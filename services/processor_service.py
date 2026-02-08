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

    # Progressive max_tokens for JSON parsing errors
    MAX_TOKENS_PROGRESSION = [1000, 2000, 3000]

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

        # LLM 메모리 절감 기법 TOP5 저장
        top5 = self.queue_manager.save_efficiency_top5(date_str)
        if top5:
            print(f'\n📊 LLM Efficiency TOP5:')
            for paper in top5:
                print(f"  {paper['rank']}. [{paper['efficiency_score']}점] {paper['title'][:50]}...")
        else:
            print(f'\n📊 LLM 메모리 절감 관련 논문 없음')

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

        # 2. Analyze with vLLM (with progressive max_tokens for JSON parsing errors)
        analysis = None

        for max_tokens in self.MAX_TOKENS_PROGRESSION:
            try:
                # Bind loop variables to avoid closure issues
                async def vllm_operation(_content=content, _content_type=content_type, _max_tokens=max_tokens):
                    return await asyncio.to_thread(
                        self.vllm_client.analyze_paper, paper, _content, _content_type, max_tokens=_max_tokens
                    )

                analysis = await self._retry_with_backoff(
                    vllm_operation, f'vLLM 분석 (max_tokens={max_tokens})', f'vLLM 분석 실패: {paper.arxiv_id}'
                )
                break  # Success - exit the loop

            except RuntimeError as e:
                error_str = str(e.__cause__) if e.__cause__ else str(e)

                # Case 1: max_token error (context overflow) - switch to Abstract
                if content_type == 'html' and 'max_tokens must be at least 1' in error_str:
                    self.logger.warning(
                        f'HTML too large for {paper.arxiv_id} ({len(content):,} chars), retrying with Abstract'
                    )
                    print(f'  - ⚠️  HTML too large ({len(content):,} chars), retrying with Abstract')

                    # Switch to Abstract
                    content = paper.summary
                    content_type = 'abstract_large'
                    print(f'  - Abstract 로드 완료 ({len(content):,} chars)')

                    # Retry with Abstract (restart max_tokens progression)
                    for max_tokens_abstract in self.MAX_TOKENS_PROGRESSION:
                        try:
                            # Bind loop variables to avoid closure issues
                            async def vllm_operation_abstract(
                                _content=content, _content_type=content_type, _max_tokens=max_tokens_abstract
                            ):
                                return await asyncio.to_thread(
                                    self.vllm_client.analyze_paper,
                                    paper,
                                    _content,
                                    _content_type,
                                    max_tokens=_max_tokens,
                                )

                            analysis = await self._retry_with_backoff(
                                vllm_operation_abstract,
                                f'vLLM 분석 (Abstract, max_tokens={max_tokens_abstract})',
                                f'vLLM 분석 실패: {paper.arxiv_id}',
                            )
                            break
                        except RuntimeError as e_abstract:
                            error_str_abstract = str(e_abstract.__cause__) if e_abstract.__cause__ else str(e_abstract)

                            # JSON parsing error with Abstract - try next max_tokens
                            if (
                                'JSON 파싱 실패' in error_str_abstract or 'Unterminated string' in error_str_abstract
                            ) and max_tokens_abstract != self.MAX_TOKENS_PROGRESSION[-1]:
                                self.logger.warning(
                                    f'JSON 파싱 실패 (Abstract, max_tokens={max_tokens_abstract}), '
                                    f'다음 시도: {self.MAX_TOKENS_PROGRESSION[self.MAX_TOKENS_PROGRESSION.index(max_tokens_abstract) + 1]}'
                                )
                                print(
                                    f'  - ⚠️  JSON 파싱 실패, max_tokens를 {max_tokens_abstract} → '
                                    f'{self.MAX_TOKENS_PROGRESSION[self.MAX_TOKENS_PROGRESSION.index(max_tokens_abstract) + 1]}로 증가'
                                )
                                continue
                            else:
                                raise

                    if analysis:
                        break  # Success with Abstract
                    else:
                        raise  # Failed even with Abstract

                # Case 2: JSON parsing error - try next max_tokens
                elif (
                    'JSON 파싱 실패' in error_str or 'Unterminated string' in error_str
                ) and max_tokens != self.MAX_TOKENS_PROGRESSION[-1]:
                    next_tokens = self.MAX_TOKENS_PROGRESSION[self.MAX_TOKENS_PROGRESSION.index(max_tokens) + 1]
                    self.logger.warning(f'JSON 파싱 실패 (max_tokens={max_tokens}), 다음 시도: {next_tokens}')
                    print(f'  - ⚠️  JSON 파싱 실패, max_tokens를 {max_tokens} → {next_tokens}로 증가')
                    continue  # Try next max_tokens

                # Case 3: Other errors or last max_tokens - fail
                else:
                    raise

        if not analysis:
            raise RuntimeError(f'vLLM 분석 실패: {paper.arxiv_id} (모든 max_tokens 시도 완료)')

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
