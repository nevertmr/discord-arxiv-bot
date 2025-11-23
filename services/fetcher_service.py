"""arXiv 논문 가져오기 서비스"""

import logging

import config
from clients.arxiv_client import ArxivClient
from core.queue_manager import QueueManager
from models.paper import Paper


class FetcherService:
    """arXiv에서 특정 날짜 논문 메타데이터를 가져와서 큐에 추가하는 서비스"""

    def __init__(self, arxiv_client: ArxivClient, queue_manager: QueueManager):
        self.arxiv_client = arxiv_client
        self.queue_manager = queue_manager
        self.logger = logging.getLogger('FetcherService')
        self.target_categories = set(config.CHANNEL_MAPPING.keys())

    async def fetch_and_enqueue_for_date(self, target_date, date_str: str):
        """특정 날짜의 논문 메타데이터를 가져와서 큐에 추가"""
        try:
            print(f'\n{"=" * 80}')
            print(f'📚 arXiv에서 {date_str} 논문 메타데이터 가져오는 중...')
            print(f'카테고리: {", ".join(config.ARXIV_CATEGORIES)}')
            print(f'{"=" * 80}\n')

            # arxiv에서 논문 메타데이터 가져오기
            self.logger.info(f'Fetch 시작: {date_str}')
            papers = self.arxiv_client.fetch_by_date(target_date)
            self.logger.info(f'총 {len(papers)}개 논문 발견')
            print(f'[FETCH] 총 {len(papers)}개 논문 발견\n')

            # 필터링 및 큐에 추가
            added_count = 0
            duplicate_count = 0
            ignored_count = 0

            for i, paper in enumerate(papers, 1):
                # 1. 카테고리 필터링
                if not self._has_target_category(paper):
                    ignored_count += 1
                    self.logger.debug(
                        f'카테고리 무시: {paper.arxiv_id} '
                        f'(primary: {paper.primary_category}, all: {paper.all_categories})'
                    )
                    continue

                # 2. 중복 체크
                if self.queue_manager.is_duplicate(paper.arxiv_id, date_str):
                    duplicate_count += 1
                    self.logger.debug(f'중복 제외: {paper.arxiv_id}')
                    continue

                # 3. pending에 메타데이터만 추가
                if self.queue_manager.add_pending(paper, date_str):
                    added_count += 1
                    self.logger.info(f'Pending 추가: {paper.full_id} (primary: {paper.primary_category})')

                if i % 10 == 0:
                    print(f'  진행 중... {i}/{len(papers)} 처리됨 (추가: {added_count})')

            self.logger.info(
                f'Fetch 완료 - 새 논문: {added_count}개, 중복: {duplicate_count}개, 카테고리 무시: {ignored_count}개'
            )
            print(f'\n{"=" * 80}')
            print('[QUEUE] Fetch 완료')
            print(f'  새 논문 추가: {added_count}개')
            print(f'  중복 제외: {duplicate_count}개')
            print(f'  카테고리 무시: {ignored_count}개')
            print(f'{"=" * 80}\n')

            return added_count

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
