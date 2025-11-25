# arXiv Discord Notifier

특정 날짜의 arXiv 논문을 자동으로 수집하고, vLLM으로 분석하여 Discord 채널에 발송하는 봇입니다.

## 주요 기능

- **날짜별 논문 수집**: arXiv에서 특정 날짜에 제출된 논문을 카테고리별로 수집
- **지연 다운로드**: 메타데이터만 먼저 수집하고, 처리 시점에 HTML 다운로드 (rate limiting 회피)
- **AI 분석**: 로컬 vLLM 서버를 활용하여 논문 요약, 방법론, 연구 맥락, 기여도 분석
- **자동 라우팅**: 논문 카테고리에 따라 적절한 Discord 채널로 자동 발송
- **중복 방지**: 이미 처리된 논문은 자동으로 건너뛰기
- **재시도 로직**: 네트워크 오류나 일시적 장애 시 자동 재시도 (각 단계별 3회, 5초 간격)

## 설계 특징

### 아키텍처

```
User Input (--date)
    ↓
arXiv API → 메타데이터 수집
    ↓
File-based Queue (pending/날짜/)
    ↓
[처리 시점]
HTML Download → vLLM Analysis
    ↓
Discord Notification (카테고리별)
    ↓
Completion (completed/날짜/)
```

### 모듈 구조

```
discord-arxiv-bot/
├── bot.py                    # 진입점 (argparse, 봇 초기화)
├── config.py                 # 환경변수 로드 및 검증
├── clients/                  # 외부 서비스 연동
│   ├── arxiv_client.py       # arXiv API + HTML 다운로드
│   ├── vllm_client.py        # vLLM 서버 통신
│   └── discord_client.py     # Discord 메시지 발송
├── core/                     # 핵심 로직
│   └── queue_manager.py      # 날짜별 파일 큐 시스템
├── services/                 # 비즈니스 로직
│   ├── fetcher_service.py    # 논문 메타데이터 수집
│   └── processor_service.py  # HTML 다운로드 + vLLM 분석 + Discord 발송
├── models/                   # 데이터 모델
│   ├── paper.py              # Paper 모델 (+ full_id 속성)
│   └── analysis.py           # Analysis 모델 (Pydantic)
└── utils/                    # 유틸리티
    └── logger.py             # 로깅 설정
```

### 핵심 설계 결정

1. **지연 HTML 다운로드** ⭐
   - Fetch 시점: 메타데이터만 수집 (빠름)
   - Process 시점: HTML 다운로드 + vLLM 분석
   - vLLM 분석이 느려서 자연스럽게 다운로드 간격 확보
   - arXiv rate limiting 회피

2. **날짜별 폴더 구조**
   - `pending/YYYY-MM-DD/`: 메타데이터만 (JSON)
   - `completed/YYYY-MM-DD/`: 메타데이터 + HTML 원문 + 분석 결과
   - 재실행 시 중복 방지 및 이어서 처리 가능

3. **HTML vs Abstract 자동 대체**
   - HTML 우선 시도 (전체 논문 내용)
   - 404 에러 → Abstract 사용 (재시도 없음)
   - Discord에 안내 메시지 표시

4. **일회성 실행**
   - 크론이나 스케줄러로 실행하는 배치 작업
   - 실시간 폴링 불필요 (arXiv는 매일 일괄 업데이트)
   - 리소스 효율적

5. **3단계 에러 처리**
   - HTML 다운로드: 3회 재시도 (5초 간격), 404는 Abstract 대체
   - vLLM 분석: 3회 재시도 (5초 간격)
   - Discord 발송: 3회 재시도 (5초 간격)
   - 각 단계 실패 시 프로그램 종료 (명확한 실패 지점)

6. **추상화 및 분리**
   - argparse는 bot.py에서 처리 (설정과 실행 로직 분리)
   - Paper 모델에 `full_id` 속성으로 arxiv_id+version 추상화
   - 설정 검증은 config.py의 `validate_config()` 함수로 분리
   - 재시도 로직은 `_retry_with_backoff()` 헬퍼 함수로 추상화 (코드 중복 제거)

## 사용법

### 설치

```bash
bash setup.sh
```

### 설정

`.env` 파일 설정:

```env
# Discord 설정
DISCORD_TOKEN=your_discord_bot_token

# 카테고리별 채널 ID
CHANNEL_CS_AI=
CHANNEL_CS_LG=
CHANNEL_CS_CV=
CHANNEL_CS_CL=
CHANNEL_CS_NE=
CHANNEL_CS_CR=

# vLLM 설정
VLLM_BASE_URL=http://192.168.31.165:8000/v1
VLLM_MODEL=/models/gpt-oss-120b
VLLM_MAX_TOKENS=1000
VLLM_TEMPERATURE=0.0
VLLM_TIMEOUT=120
VLLM_MAX_RETRIES=3
```

### 실행

```bash
# run.sh 사용
bash run.sh --date 2025-11-24

# 직접 실행
python bot.py --date 2025-11-24
```

## 출력 예시

```
=== arXiv Discord Notifier ===
날짜: 2025-11-22

[FETCH] 총 87개 논문 메타데이터 가져오는 중...
[FETCH] 총 87개 논문 발견
[QUEUE] 새 논문 추가: 85개

📋 85개 논문 처리 시작

[01/85] 2311.12345v1
  - https://arxiv.org/html/2311.12345v1
  - 제목: Attention Is All You Need
  - 카테고리: cs.AI
  - HTML 다운로드 중...
  - HTML 로드 완료 (366,776 chars)
  - vLLM 분석 중...
    vLLM 응답 (html, 366,776 chars): {"summary": ...}
  - Discord 발송 완료 (cs.AI)

[02/85] 2311.12346v1
  - HTML 다운로드 중...
  - Abstract 로드 완료 (1,234 chars)  # HTML 없는 경우
  - vLLM 분석 중...
  - Discord 발송 완료 (cs.CV)

...

=== 완료 ===
총 처리: 85개
성공: 85개

[통계]
  cs.AI: 30
  cs.CV: 25
  cs.LG: 20
  cs.CL: 10
```

## Discord 알림 형식

논문별로 Embed 메시지가 발송됩니다:

- 제목 및 arXiv 링크
- 저자, 카테고리, 발행일
- AI 분석 결과 (요약, 방법론, 연구 맥락, 기여도)
- HTML/PDF/Abstract 링크
- Abstract 기반 분석인 경우 안내 메시지

## 기술 스택

- Python 3.9+
- discord.py: Discord 봇 API
- arxiv: arXiv API 클라이언트
- openai: vLLM 서버 통신 (OpenAI-compatible)
- pydantic: 구조화된 출력 검증
- requests: HTTP 통신 (HTML 다운로드)

## 개발 환경

```bash
# 코드 품질 검사 및 포맷팅
bash lint.sh
```

## 데이터 구조

```
data/
├── pending/                 # 처리 대기 (메타데이터만)
│   └── 2025-11-22/
│       ├── 2311.12345.json  # Paper 메타데이터
│       └── 2311.12346.json
└── completed/               # 처리 완료
    └── 2025-11-22/
        ├── 2311.12345.json  # 메타데이터 + 분석 결과
        ├── 2311.12345.txt   # HTML 원문 또는 Abstract
        ├── 2311.12346.json
        ├── 2311.12346.txt
        └── stats.json       # 카테고리별 통계
```

## Rate Limiting 대응

- **arXiv API**: arxiv 라이브러리가 자동으로 대기 (페이지당 약 3초)
- **HTML 다운로드**: vLLM 분석 시간(30초~1분)으로 자연스럽게 간격 확보
- 각 단계별 재시도 시 5초 대기로 추가 안전

## 라이선스

MIT License
