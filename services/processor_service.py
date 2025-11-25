"""Paper processing service"""

import asyncio
import logging

from clients.arxiv_client import ArxivClient
from clients.discord_client import DiscordClient
from clients.vllm_client import VLLMClient
from core.queue_manager import QueueManager
from models.paper import Paper


class ProcessorService:
    """Service to fetch papers from queue, download HTML, analyze with vLLM, and send to Discord"""

    # Retry delay in seconds
    RETRY_DELAY_SECONDS = 5

    def __init__(
        self,
        arxiv_client: ArxivClient,
        vllm_client: VLLMClient,
        discord_client: DiscordClient,
        queue_manager: QueueManager,
        max_retries: int = 3,
    ):
        self.arxiv_client = arxiv_client
        self.vllm_client = vllm_client
        self.discord_client = discord_client
        self.queue_manager = queue_manager
        self.max_retries = max_retries
        self.logger = logging.getLogger('ProcessorService')

    async def process_all_for_date(self, date_str: str):
        """Process all papers for the given date"""
        papers = self.queue_manager.get_pending_papers(date_str)
        total = len(papers)

        if total == 0:
            self.logger.info(f'{date_str}: 처리할 논문 없음')
            print(f'\n{"=" * 80}')
            print(f'{date_str}: 처리할 논문이 없습니다.')
            print(f'{"=" * 80}\n')
            return

        self.logger.info(f'{date_str}: {total}개 논문 처리 시작')
        print(f'\n{"=" * 80}')
        print(f'📋 {total}개 논문 처리 시작')
        print(f'{"=" * 80}\n')

        success_count = 0
        failed_papers = []

        for idx, paper in enumerate(papers, 1):
            success = await self._process_single_paper(paper, date_str, idx, total)
            if success:
                success_count += 1
            else:
                failed_papers.append(paper.arxiv_id)

        # Final results
        print(f'\n{"=" * 80}')
        print('=== 완료 ===')
        print(f'총 처리: {total}개')
        print(f'성공: {success_count}개')
        if failed_papers:
            print(f'실패: {len(failed_papers)}개')
            print(f'실패 논문: {", ".join(failed_papers)}')
        print(f'{"=" * 80}\n')

        self.logger.info(f'처리 완료 - 성공: {success_count}/{total}')

    async def _retry_with_backoff(self, operation_func, operation_name: str, error_message: str):
        """Helper function for retry logic with backoff"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(f'{operation_name} 시도 {attempt}/{self.max_retries}')
                print(f'  - {operation_name} 중... (시도 {attempt}/{self.max_retries})')

                result = await operation_func()
                return result

            except Exception as e:
                # max_token error should not be retried - fail immediately
                if 'max_tokens must be at least 1' in str(e):
                    self.logger.error(f'{operation_name} max_token Error')
                    print('  - max_token Error')
                    raise RuntimeError(f'{error_message}') from e

                self.logger.error(f'{operation_name} 에러 (시도 {attempt}/{self.max_retries}): {e}')
                print(f'  - {operation_name} 에러: {e}')

                if attempt < self.max_retries:
                    self.logger.info(f'재시도 대기 중... ({self.RETRY_DELAY_SECONDS}초)')
                    print(f'  - {self.RETRY_DELAY_SECONDS}초 후 재시도...')
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                else:
                    self.logger.error(f'{error_message} (최대 재시도 초과)')
                    print(f'  - ❌ {error_message}: 최대 재시도 초과')
                    print('\n프로그램을 종료합니다.\n')
                    raise RuntimeError(f'{error_message} ({self.max_retries}회 시도)') from e

    async def _process_single_paper(self, paper: Paper, date_str: str, idx: int, total: int) -> bool:
        """Process a single paper"""
        self.logger.info(f'처리 시작 [{idx}/{total}]: {paper.full_id}')

        print(f'\n{"=" * 80}')
        print(f'[{idx:02d}/{total:02d}] {paper.full_id}')
        print(f'  - {paper.html_url}')
        print(f'  - 제목: {paper.title}')
        print(f'  - 카테고리: {paper.primary_category}')
        print(f'{"=" * 80}')

        # 1. Download HTML
        async def download_operation():
            content, content_type = await asyncio.to_thread(self.arxiv_client.download_html, paper)
            content_label = 'HTML' if content_type == 'html' else 'Abstract'
            print(f'  - {content_label} 로드 완료 ({len(content):,} chars)')
            return content, content_type

        content, content_type = await self._retry_with_backoff(
            download_operation, 'HTML 다운로드', f'다운로드 실패: {paper.arxiv_id}'
        )

        # 2. Analyze with vLLM
        async def vllm_operation():
            return await asyncio.to_thread(self.vllm_client.analyze_paper, paper, content, content_type)

        try:
            analysis = await self._retry_with_backoff(vllm_operation, 'vLLM 분석', f'vLLM 분석 실패: {paper.arxiv_id}')
        except RuntimeError as e:
            # If max_token error with HTML, retry with Abstract
            if content_type == 'html' and e.__cause__ and 'max_tokens must be at least 1' in str(e.__cause__):
                self.logger.warning(
                    f'HTML too large for {paper.arxiv_id} ({len(content):,} chars), retrying with Abstract'
                )
                print(f'  - ⚠️  HTML too large ({len(content):,} chars), retrying with Abstract')

                # Switch to Abstract
                content = paper.summary
                content_type = 'abstract_large'  # Mark as fallback due to size
                print(f'  - Abstract 로드 완료 ({len(content):,} chars)')

                # Retry with Abstract
                async def vllm_operation_abstract():
                    return await asyncio.to_thread(self.vllm_client.analyze_paper, paper, content, content_type)

                analysis = await self._retry_with_backoff(
                    vllm_operation_abstract, 'vLLM 분석 (Abstract)', f'vLLM 분석 실패: {paper.arxiv_id}'
                )
            else:
                raise

        # 3. Send to Discord
        async def discord_operation():
            success = await self.discord_client.send_paper_notification(paper, analysis, content_type)
            if not success:
                raise RuntimeError('Discord 발송이 False를 반환했습니다')
            return success

        await self._retry_with_backoff(discord_operation, 'Discord 발송', f'Discord 발송 실패: {paper.arxiv_id}')

        # Mark as completed
        self.queue_manager.complete_processing(paper, content, content_type, analysis, date_str)
        self.logger.info(f'처리 완료 [{idx}/{total}]: {paper.arxiv_id}')
        print(f'  - ✓ Discord 발송 완료 ({paper.primary_category})')
        return True
