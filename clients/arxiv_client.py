"""arXiv API 클라이언트"""
import arxiv
from typing import List
import logging

from models.paper import Paper


class ArxivClient:
    """arXiv API 래퍼"""
    
    def __init__(self, categories: List[str]):
        self.categories = categories
        self.logger = logging.getLogger('ArxivClient')
    
    def fetch_recent(self, max_results: int = 100) -> List[Paper]:
        """최신 논문 가져오기"""
        query = "cat:(" + " OR ".join(self.categories) + ")"
        
        self.logger.info(f"arxiv 검색 시작: {query}, max_results={max_results}")
        print(f"\n{'='*80}")
        print(f"📚 arXiv에서 최신 논문 가져오는 중...")
        print(f"카테고리: {', '.join(self.categories)}")
        print(f"최대 결과: {max_results}개")
        print(f"{'='*80}\n")
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for i, result in enumerate(search.results(), 1):
            paper = Paper.from_arxiv_result(result)
            papers.append(paper)
            
            if i % 10 == 0:
                print(f"  진행 중... {i}개 로드 완료")
        
        self.logger.info(f"총 {len(papers)}개 논문 로드 완료")
        print(f"\n✓ 총 {len(papers)}개 논문 로드 완료\n")
        
        return papers

