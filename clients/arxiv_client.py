"""arXiv API 클라이언트"""

import logging
from datetime import datetime

import arxiv
import requests

from models.paper import Paper


class ArxivClient:
    """arXiv API 래퍼"""

    def __init__(self, categories: list[str]):
        self.categories = categories
        self.logger = logging.getLogger('ArxivClient')

    def fetch_by_date(self, target_date: datetime.date) -> list[Paper]:
        """특정 날짜에 제출된 논문 가져오기"""
        # arXiv는 매일 오전에 전날 제출된 논문을 공개
        # submittedDate를 사용하여 해당 날짜의 논문만 가져오기
        date_str = target_date.strftime('%Y%m%d')
        query = f'cat:({" OR ".join(self.categories)}) AND submittedDate:[{date_str}0000 TO {date_str}2359]'

        self.logger.info(f'arXiv 검색 시작: 날짜={target_date}, 카테고리={self.categories}')

        search = arxiv.Search(
            query=query,
            max_results=1000,  # 하루 논문은 보통 1000개 이하
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        papers = []
        for result in search.results():
            paper = Paper.from_arxiv_result(result)
            papers.append(paper)

        self.logger.info(f'총 {len(papers)}개 논문 발견')
        return papers

    def download_html(self, paper: Paper) -> tuple[str, str]:
        """
        논문 HTML 다운로드 (실패 시 Abstract 사용)

        Returns:
            tuple[str, str]: (content, content_type)
            - content: HTML 전문 또는 Abstract
            - content_type: 'html' 또는 'abstract'
        """
        try:
            self.logger.info(f'HTML 다운로드 시작: {paper.html_url}')
            response = requests.get(paper.html_url, timeout=30)
            response.raise_for_status()

            html_content = response.text
            self.logger.info(f'HTML 다운로드 완료: {paper.full_id} ({len(html_content)} bytes)')
            return html_content, 'html'

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.warning(f'HTML 없음 - Abstract 사용: {paper.full_id}')
                return paper.summary, 'abstract'
            raise
        except Exception as e:
            self.logger.error(f'HTML 다운로드 실패: {paper.html_url}, {e}')
            raise
