# arXiv 논문 자동 알림 Discord 봇

arXiv 최신 AI/ML 논문을 수집하고 로컬 vLLM으로 분석해서 Discord 카테고리별 채널에 자동 발송하는 봇입니다.

## 기능

- arXiv에서 1분마다 6개 카테고리 논문 수집 (cs.AI, cs.LG, cs.CV, cs.CL, cs.NE, cs.CR)
- vLLM으로 논문 분석 및 한국어 요약
- Discord Embed로 카테고리별 채널 자동 발송
- Secondary 카테고리 지원 (primary가 없으면 secondary로 라우팅)
- 파일 기반 큐 시스템 (중복 방지, 재시작 복구)
- 일일 통계 자동 생성

## 알림 내용

- 논문 제목 (링크)
- 저자
- 카테고리
- 발행일
- AI 분석 (요약, 방법론, 연구 맥락, 기여점)
- arXiv/PDF 링크

## 구조

```
├── bot.py                    # Discord 봇 메인
├── config.py                 # 환경 설정
├── models/                   # 데이터 모델
├── clients/                  # API 클라이언트 (arXiv, vLLM, Discord)
├── core/                     # 큐 관리
├── services/                 # 비즈니스 로직
│   ├── fetcher_service.py   # 논문 수집
│   └── processor_service.py # 논문 처리
└── utils/                    # 로깅, 통계
```

### 주요 설계

- **Producer-Consumer**: Fetcher와 Processor가 독립 실행
- **파일 기반 큐**: pending → processing → completed (날짜별 JSON)
- **비동기 처리**: vLLM을 별도 스레드로 실행하여 Discord heartbeat 블로킹 방지
- **3단계 필터링**: Fetcher(카테고리 필터) → Processor(처리) → Discord(채널 라우팅)

## 실행

```bash
# 설치
uv sync

# 실행
uv run python bot.py
```

### 환경 변수 (.env)

```bash
DISCORD_TOKEN=your_token
CHANNEL_CS_AI=channel_id
CHANNEL_CS_LG=channel_id
# ... 다른 채널들

VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=/models/gpt-oss-120b
CHECK_INTERVAL_MINUTES=1
```


