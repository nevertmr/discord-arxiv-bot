"""arXiv 논문 가져오기 서비스"""
import logging
from typing import List

from clients.arxiv_client import ArxivClient
from core.queue_manager import QueueManager
from models.paper import Paper


class FetcherService:
    """arXiv에서 논문을 가져와서 큐에 추가하는 서비스"""
    
    def __init__(self, arxiv_client: ArxivClient, queue_manager: QueueManager):
        self.arxiv_client = arxiv_client
        self.queue_manager = queue_manager
        self.logger = logging.getLogger('FetcherService')
    
    async def fetch_and_enqueue(self, max_results: int = 100, is_initial: bool = False):
        """논문을 가져와서 큐에 추가"""
        try:
            # arxiv에서 논문 가져오기
            papers = self.arxiv_client.fetch_recent(max_results=max_results)
            
            if is_initial:
                self.logger.info(f"초기 실행: {len(papers)}개 논문 처리 중...")
            
            # 중복 제거 및 큐에 추가
            added_count = 0
            duplicate_count = 0
            
            for paper in papers:
                # Primary 카테고리만 처리
                published_date = paper.published.strftime('%Y-%m-%d')
                
                # 중복 체크
                if self.queue_manager.is_duplicate(paper.arxiv_id, published_date):
                    duplicate_count += 1
                    continue
                
                # pending에 추가
                if self.queue_manager.add_pending(paper):
                    added_count += 1
            
            self.logger.info(
                f"Fetch 완료 - 새 논문: {added_count}개, 중복: {duplicate_count}개"
            )
            print(f"\n{'='*80}")
            print(f"📊 Fetch 결과")
            print(f"  새 논문: {added_count}개")
            print(f"  중복 제외: {duplicate_count}개")
            print(f"  대기 큐: {self.queue_manager.get_pending_count()}개")
            print(f"{'='*80}\n")
            
        except Exception as e:
            self.logger.error(f"Fetch 실패: {e}")
            raise

