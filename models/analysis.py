"""논문 분석 결과 모델"""

from pydantic import BaseModel, Field


class Analysis(BaseModel):
    """vLLM 논문 분석 결과 (Structured Output)"""

    summary: str = Field(description='3-4문장으로 핵심 내용 요약')
    methodology: str = Field(description='주요 기술이나 방법론 설명')
    context: str = Field(description='연구 분야 및 트렌드 설명')
    contribution: str = Field(description='기대 효과 또는 기여점')
    efficiency_score: int = Field(description='LLM 메모리 절감 기법 관련도 점수 (0-10)')
