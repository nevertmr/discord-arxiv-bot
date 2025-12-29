"""vLLM API 클라이언트"""

import json
import logging

from openai import OpenAI

from models.analysis import Analysis
from models.paper import Paper


class VLLMClient:
    """vLLM API 래퍼"""

    def __init__(self, base_url: str, model: str, max_tokens: int, temperature: float, timeout: int):
        self.client = OpenAI(base_url=base_url, api_key='EMPTY', timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logging.getLogger('VLLMClient')

    def analyze_paper(self, paper: Paper, content: str, content_type: str, max_tokens: int = None) -> Analysis:
        """논문 분석 (Structured Output)"""
        prompt = self._create_prompt(paper, content, content_type)

        # Use provided max_tokens or default
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        self.logger.info(
            f'vLLM 분석 요청: {paper.arxiv_id} ({content_type}, {len(content)} chars, max_tokens={tokens})'
        )

        # Streaming 응답
        print(f'    vLLM 응답 ({content_type}, {len(content):,} chars, max_tokens={tokens}): ', end='', flush=True)
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
            max_tokens=tokens,
            temperature=self.temperature,
            response_format={'type': 'json_object'},
        )

        full_response = ''
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end='', flush=True)
                full_response += content
        print('\n')

        # JSON 파싱
        try:
            response_data = json.loads(full_response)
            analysis = Analysis(**response_data)
            self.logger.info(f'vLLM 분석 완료: {paper.arxiv_id}')
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f'JSON 파싱 실패: {e}')
            raise ValueError(f'vLLM 응답 파싱 실패: {e}') from e

    def _create_prompt(self, paper: Paper, content: str, content_type: str) -> str:
        """프롬프트 생성"""
        authors_str = ', '.join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors_str += f' 외 {len(paper.authors) - 5}명'

        content_label = 'HTML 전문' if content_type == 'html' else 'Abstract'
        content_note = (
            '논문 HTML의 내용' if content_type == 'html' else 'Abstract의 내용 (HTML이 제공되지 않아 Abstract만 사용)'
        )

        return f"""다음 arXiv 논문을 분석해주세요. 논문의 {content_label}이 제공됩니다.

=== 메타데이터 ===
제목: {paper.title}
저자: {authors_str}
카테고리: {paper.primary_category}
발행일: {paper.published.strftime('%Y-%m-%d')}
arXiv ID: {paper.full_id}

=== 논문 {content_label} ===
{content}

=== 분석 요청 ===
**중요: 반드시 한국어로 답변하세요. 영어가 아닌 한국어로만 작성해야 합니다.**

위의 논문 내용을 읽고 다음 형식으로 JSON으로만 답변해주세요 (트랜스포머 아키텍처를 이해하는 AI 연구자 수준):

{{
  "summary": "3-4문장으로 핵심 내용을 한국어로 요약",
  "methodology": "주요 기술이나 방법론을 한국어로 설명",
  "context": "연구 분야 및 트렌드를 한국어로 설명",
  "contribution": "기대 효과 또는 기여점을 한국어로 설명"
}}

**다시 한번 강조: 모든 필드의 값은 반드시 한국어로 작성해야 합니다. 하지만 한국어로 설명이 어려운 영어단어나 영어단어가 메인으로 쓰이는 영어단어는 영어로 표기해도 됩니다.**
모르는 내용은 추측하지 말고, 제공된 {content_note}에만 근거하여 작성하세요."""
