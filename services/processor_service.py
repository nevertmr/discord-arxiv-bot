"""논문 처리 서비스"""

import asyncio
import logging

from clients.discord_client import DiscordClient
from clients.vllm_client import VLLMClient
from core.queue_manager import QueueManager
from models.paper import Paper


class ProcessorService:
    """큐에서 논문을 가져와 vLLM으로 분석하고 Discord에 발송하는 서비스"""

    def __init__(
        self,
        vllm_client: VLLMClient,
        discord_client: DiscordClient,
        queue_manager: QueueManager,
        max_retries: int = 3,
    ):
        self.vllm_client = vllm_client
        self.discord_client = discord_client
        self.queue_manager = queue_manager
        self.max_retries = max_retries
        self.logger = logging.getLogger('ProcessorService')

    async def process_all_for_date(self, date_str: str):
        """해당 날짜의 모든 논문 처리"""
        papers_with_content = self.queue_manager.get_pending_papers(date_str)
        total = len(papers_with_content)

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

        for idx, (paper, content, content_type) in enumerate(papers_with_content, 1):
            success = await self._process_single_paper(paper, content, content_type, date_str, idx, total)
            if success:
                success_count += 1
            else:
                failed_papers.append(paper.arxiv_id)

        # 최종 결과
        print(f'\n{"=" * 80}')
        print('=== 완료 ===')
        print(f'총 처리: {total}개')
        print(f'성공: {success_count}개')
        if failed_papers:
            print(f'실패: {len(failed_papers)}개')
            print(f'실패 논문: {", ".join(failed_papers)}')
        print(f'{"=" * 80}\n')

        self.logger.info(f'처리 완료 - 성공: {success_count}/{total}')

    async def _process_single_paper(
        self, paper: Paper, content: str, content_type: str, date_str: str, idx: int, total: int
    ) -> bool:
        """단일 논문 처리"""
        self.logger.info(f'처리 시작 [{idx}/{total}]: {paper.full_id}')

        content_label = 'HTML' if content_type == 'html' else 'Abstract'
        print(f'\n{"=" * 80}')
        print(f'[{idx:02d}/{total:02d}] {paper.full_id}')
        print(f'  - {paper.html_url}')
        print(f'  - 제목: {paper.title}')
        print(f'  - 카테고리: {paper.primary_category}')
        print(f'{"=" * 80}')
        print(f'  - {content_label} 로드 완료')

        # vLLM으로 분석 (재시도 로직)
        analysis = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(f'vLLM 시도 {attempt}/{self.max_retries}: {paper.arxiv_id}')
                print(f'  - vLLM 분석 중... (시도 {attempt}/{self.max_retries})')

                # Discord heartbeat 블로킹 방지
                analysis = await asyncio.to_thread(self.vllm_client.analyze_paper, paper, content, content_type)
                break

            except Exception as e:
                self.logger.error(f'vLLM 에러 (시도 {attempt}/{self.max_retries}): {e}')
                print(f'  - vLLM 에러: {e}')

                if attempt < self.max_retries:
                    self.logger.info('재시도 대기 중... (5초)')
                    print('  - 5초 후 재시도...')
                    await asyncio.sleep(5)
                else:
                    self.logger.error(f'논문 처리 실패 (최대 재시도 초과): {paper.arxiv_id}')
                    print('  - ❌ 처리 실패: 최대 재시도 초과')
                    print('\n프로그램을 종료합니다.\n')
                    raise RuntimeError(f'vLLM 분석 실패 (3회 시도): {paper.arxiv_id}') from e

        if not analysis:
            return False

        # Discord 발송 (재시도)
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f'  - Discord 발송 중... (시도 {attempt}/{self.max_retries})')
                success = await self.discord_client.send_paper_notification(paper, analysis, content_type)

                if success:
                    # 완료 처리
                    self.queue_manager.complete_processing(paper, content, content_type, analysis, date_str)
                    self.logger.info(f'처리 완료 [{idx}/{total}]: {paper.arxiv_id}')
                    print(f'  - ✓ Discord 발송 완료 ({paper.primary_category})')
                    return True
                else:
                    raise RuntimeError('Discord 발송 실패')

            except Exception as e:
                self.logger.error(f'Discord 발송 에러 (시도 {attempt}/{self.max_retries}): {e}')
                print(f'  - Discord 에러: {e}')

                if attempt < self.max_retries:
                    print('  - 5초 후 재시도...')
                    await asyncio.sleep(5)
                else:
                    self.logger.error(f'Discord 발송 실패 (최대 재시도 초과): {paper.arxiv_id}')
                    print('  - ❌ Discord 발송 실패: 최대 재시도 초과')
                    print('\n프로그램을 종료합니다.\n')
                    raise RuntimeError(f'Discord 발송 실패 (3회 시도): {paper.arxiv_id}') from e

        return False
