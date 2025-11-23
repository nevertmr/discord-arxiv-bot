"""논문 데이터 모델"""

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class Paper:
    """arXiv 논문 데이터 클래스"""

    arxiv_id: str
    version: str  # v1, v2 등
    title: str
    authors: list[str]
    primary_category: str
    all_categories: list[str]
    published: datetime
    summary: str
    url: str
    pdf_url: str
    html_url: str  # HTML export URL

    @classmethod
    def from_arxiv_result(cls, result):
        """arxiv.Result 객체를 Paper로 변환"""
        # entry_id 예: http://arxiv.org/abs/2311.12345v1
        full_id = result.entry_id.split('/')[-1]  # 2311.12345v1

        # arxiv_id와 version 분리
        if 'v' not in full_id:
            raise ValueError(f'arXiv ID에 버전 정보가 없습니다: {full_id}')

        parts = full_id.split('v')
        arxiv_id = parts[0]  # 2311.12345
        version = f'v{parts[1]}'  # v1

        html_url = f'https://arxiv.org/html/{arxiv_id}{version}'

        return cls(
            arxiv_id=arxiv_id,
            version=version,
            title=result.title.strip(),
            authors=[author.name for author in result.authors],
            primary_category=result.primary_category,
            all_categories=result.categories,
            published=result.published,
            summary=result.summary.strip().replace('\n', ' '),
            url=result.entry_id,
            pdf_url=result.pdf_url,
            html_url=html_url,
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

    @property
    def full_id(self) -> str:
        """전체 ID (arxiv_id + version)"""
        return f'{self.arxiv_id}{self.version}'
