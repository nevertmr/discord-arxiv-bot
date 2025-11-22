"""arXiv 논문 가져오기 서비스"""

import logging

import config
from clients.arxiv_client import ArxivClient
from core.queue_manager import QueueManager
from models.paper import Paper


class FetcherService:
    """arXiv에서 논문을 가져와서 큐에 추가하는 서비스"""

    def __init__(self, arxiv_client: ArxivClient, queue_manager: QueueManager):
        self.arxiv_client = arxiv_client
        self.queue_manager = queue_manager
        self.logger = logging.getLogger('FetcherService')
        self.target_categories = set(config.CHANNEL_MAPPING.keys())

    async def fetch_and_enqueue(self, max_results: int = 100, is_initial: bool = False):
        """논문을 가져와서 큐에 추가"""
        try:
            # arxiv에서 논문 가져오기
            papers = self.arxiv_client.fetch_recent(max_results=max_results)

            if is_initial:
                self.logger.info(f'초기 실행: {len(papers)}개 논문 처리 중...')

            # 중복 제거 및 큐에 추가
            added_count = 0
            duplicate_count = 0
            ignored_count = 0

            for paper in papers:
                published_date = paper.published.strftime('%Y-%m-%d')

                # 1. 카테고리 필터링: primary 또는 secondary 중 하나라도 매칭되어야 함
                if not self._has_target_category(paper):
                    ignored_count += 1
                    self.logger.debug(
                        f'카테고리 무시: {paper.arxiv_id} '
                        f'(primary: {paper.primary_category}, all: {paper.all_categories})'
                    )
                    continue

                # 2. 중복 체크
                if self.queue_manager.is_duplicate(paper.arxiv_id, published_date):
                    duplicate_count += 1
                    continue

                # 3. pending에 추가
                if self.queue_manager.add_pending(paper):
                    added_count += 1
                    self.logger.debug(f'Pending 추가: {paper.arxiv_id} (primary: {paper.primary_category})')

            self.logger.info(
                f'Fetch 완료 - 새 논문: {added_count}개, 중복: {duplicate_count}개, 카테고리 무시: {ignored_count}개'
            )
            print(f'\n{"=" * 80}')
            print('📊 Fetch 결과')
            print(f'  새 논문: {added_count}개')
            print(f'  중복 제외: {duplicate_count}개')
            print(f'  카테고리 무시: {ignored_count}개')
            print(f'  대기 큐: {self.queue_manager.get_pending_count()}개')
            print(f'{"=" * 80}\n')

        except Exception as e:
            self.logger.error(f'Fetch 실패: {e}')
            raise

    def _has_target_category(self, paper: Paper) -> bool:
        """
        논문이 처리 대상 카테고리를 포함하는지 확인
        primary 또는 all_categories 중 하나라도 매칭되면 True
        """
        # Primary 카테고리가 target에 있는지 확인
        if paper.primary_category in self.target_categories:
            return True

        # all_categories 중 하나라도 target에 있는지 확인
        for category in paper.all_categories:
            if category in self.target_categories:
                return True

        return False
