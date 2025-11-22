# arXiv 논문 자동 알림 Discord 봇

arXiv에서 최신 AI/ML 논문을 자동으로 수집하고, vLLM으로 분석한 후 Discord 채널별로 자동 발송하는 봇입니다.

## 주요 기능

- arXiv에서 5개 카테고리(cs.AI, cs.LG, cs.CV, cs.CL, cs.NE) 최신 논문 자동 수집
- 로컬 vLLM 서버를 활용한 논문 자동 분석 및 한국어 요약
- 논문 카테고리별 Discord 채널 자동 발송
- 파일 기반 큐 시스템으로 안정적인 처리
- 중복 방지 및 재시작 시 자동 복구
- 일일 통계 자동 생성

## 시스템 요구사항

- Python 3.9 이상
- Discord 봇 토큰
- vLLM 서버 (로컬 또는 원격)
- uv 패키지 매니저 (권장)

## 설치 방법

### 1. 저장소 클론 및 의존성 설치

```bash
cd discord-arxiv-bot

# uv 사용 (권장)
uv venv
source .venv/bin/activate
uv pip install discord.py python-dotenv arxiv openai pydantic

# 또는 pip 사용
pip install -r requirements.txt
```

### 2. Discord 봇 설정

#### 2-1. 개발자 포털 설정

1. Discord Developer Portal 접속
   https://discord.com/developers/applications

2. Bot 메뉴에서 MESSAGE CONTENT INTENT 활성화

3. OAuth2 - URL Generator에서 봇 초대 URL 생성
   - SCOPES: bot
   - BOT PERMISSIONS:
     - Send Messages
     - Read Messages/View Channels
     - Embed Links

4. 생성된 URL로 봇을 서버에 초대

#### 2-2. 채널 ID 확인

1. Discord 설정 - 고급 - 개발자 모드 활성화
2. 각 채널 우클릭 - ID 복사

### 3. 환경 변수 설정

`.env` 파일 생성:

```bash
# Discord 설정
DISCORD_TOKEN=your_discord_bot_token_here

# 카테고리별 채널 ID
CHANNEL_CS_AI=1234567890123456789
CHANNEL_CS_LG=1234567890123456789
CHANNEL_CS_CV=1234567890123456789
CHANNEL_CS_CL=1234567890123456789
CHANNEL_CS_NE=1234567890123456789

# arXiv 설정
CHECK_INTERVAL_MINUTES=1
INITIAL_FETCH_COUNT=100

# vLLM 설정
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=/models/gpt-oss-120b
VLLM_MAX_TOKENS=1000
VLLM_TEMPERATURE=0.0
VLLM_TIMEOUT=120
VLLM_MAX_RETRIES=3
VLLM_CONSECUTIVE_FAILURE_LIMIT=3
```

## 실행 방법

### 봇 실행

```bash
# 가상환경 활성화
source .venv/bin/activate

# 봇 실행
python bot.py
```

또는 실행 스크립트 사용:

```bash
bash run.sh
```

### 초기 실행

처음 실행하면 자동으로 최신 100개 논문을 가져와서 순차적으로 처리합니다.
이후에는 1분마다 새로운 논문만 확인하여 처리합니다.

## 프로젝트 구조

```
discord-arxiv-bot/
├── bot.py                      # 메인 실행 파일
├── config.py                   # 설정 관리
│
├── core/                       # 핵심 인프라
│   └── queue_manager.py        # 파일 기반 큐 시스템
│
├── models/                     # 데이터 모델
│   ├── paper.py                # 논문 데이터 클래스
│   └── analysis.py             # 분석 결과 모델
│
├── clients/                    # 외부 API 클라이언트
│   ├── arxiv_client.py         # arXiv API 래퍼
│   ├── vllm_client.py          # vLLM API 래퍼
│   └── discord_client.py       # Discord 발송 래퍼
│
├── services/                   # 비즈니스 로직
│   ├── fetcher_service.py      # 논문 수집 서비스
│   └── processor_service.py    # 논문 처리 서비스
│
├── utils/                      # 유틸리티
│   ├── logger.py               # 로깅 설정
│   └── stats.py                # 통계 생성
│
├── data/                       # 데이터 저장소
│   ├── pending/                # 대기 중인 논문
│   ├── processing.json         # 현재 처리 중
│   └── completed/              # 완료된 논문 (날짜별)
│
└── logs/                       # 로그 파일
```

## 동작 원리

### 1. 논문 수집 (Fetcher)

- 1분마다 arXiv API 호출
- 5개 카테고리에서 최신 논문 검색
- 중복 확인 후 pending 큐에 추가

### 2. 논문 처리 (Processor)

- pending 큐에서 논문을 시간순으로 가져옴
- vLLM으로 논문 분석 (한국어 요약)
- Discord 채널에 발송
- completed에 저장

### 3. 에러 처리

- vLLM 실패 시 3번까지 재시도
- 3개 논문이 연속으로 실패하면 봇 종료
- 재시작 시 processing 상태 자동 복구

### 4. 통계 생성

- 날짜가 바뀔 때 전날 통계 자동 생성
- 카테고리별 논문 수 집계

## 데이터 파일 구조

### pending (대기 큐)
```
data/pending/20240115_103000_2401.12345.json
```

### completed (완료)
```json
{
  "stats": {
    "date": "2024-01-15",
    "total": 42,
    "by_category": {
      "cs.CV": 15,
      "cs.LG": 12,
      "cs.AI": 10,
      "cs.CL": 3,
      "cs.NE": 2
    }
  },
  "papers": [
    {
      "arxiv_id": "2401.12345",
      "title": "...",
      "llm_analysis": {
        "summary": "...",
        "methodology": "...",
        "context": "...",
        "contribution": "..."
      }
    }
  ]
}
```

## vLLM 서버 설정

봇은 OpenAI 호환 API를 사용하는 vLLM 서버와 연동됩니다.

### vLLM 서버 예제

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY"
)

response = client.chat.completions.create(
    model="/models/gpt-oss-120b",
    messages=[{"role": "user", "content": "..."}],
    stream=True,
    max_tokens=1000,
    temperature=0.0,
    response_format={"type": "json_object"}
)
```

## 문제 해결

### 봇이 메시지에 반응하지 않아요

- MESSAGE CONTENT INTENT가 활성화되어 있는지 확인
- 봇이 해당 채널을 볼 수 있는 권한이 있는지 확인

### vLLM 연결 실패

- VLLM_BASE_URL이 올바른지 확인
- vLLM 서버가 실행 중인지 확인
- 방화벽 설정 확인

### 중복 논문이 발송돼요

- data/completed/ 디렉토리의 날짜별 파일 확인
- 중복 체크는 논문 게시일 기준으로 동작

### 큐가 계속 쌓여요

- vLLM 서버 성능 확인
- VLLM_TIMEOUT 값 조정
- 로그에서 에러 확인

## 로그 확인

로그는 `logs/` 디렉토리에 날짜별로 저장됩니다:

```bash
tail -f logs/bot_2024-01-15.log
```

## 라이선스

MIT License

## 기여

이슈 및 풀 리퀘스트를 환영합니다.
