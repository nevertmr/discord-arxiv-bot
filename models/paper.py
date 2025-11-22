"""논문 데이터 모델"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List


@dataclass
class Paper:
    """arXiv 논문 데이터 클래스"""
    arxiv_id: str
    title: str
    authors: List[str]
    primary_category: str
    all_categories: List[str]
    published: datetime
    summary: str
    url: str
    pdf_url: str
    
    @classmethod
    def from_arxiv_result(cls, result):
        """arxiv.Result 객체를 Paper로 변환"""
        arxiv_id = result.entry_id.split('/')[-1].replace('v', '').split('v')[0]
        
        return cls(
            arxiv_id=arxiv_id,
            title=result.title.strip(),
            authors=[author.name for author in result.authors],
            primary_category=result.primary_category,
            all_categories=result.categories,
            published=result.published,
            summary=result.summary.strip().replace('\n', ' '),
            url=result.entry_id,
            pdf_url=result.pdf_url
        )
    
    def to_dict(self) -> dict:
        """JSON 직렬화를 위한 딕셔너리 변환"""
        data = asdict(self)
        data['published'] = self.published.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """딕셔너리에서 Paper 객체 생성"""
        data = data.copy()
        data['published'] = datetime.fromisoformat(data['published'])
        return cls(**data)

