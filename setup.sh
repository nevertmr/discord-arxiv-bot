#!/bin/bash
# arXiv Discord 봇 설치 스크립트

echo "arXiv Discord 봇 설치를 시작합니다..."
echo ""

# uv 설치 확인
if ! command -v uv &> /dev/null; then
    echo "uv가 설치되어 있지 않습니다. 설치를 시작합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "uv 설치가 완료되었습니다!"
    echo "터미널을 재시작하거나 다음 명령어를 실행하세요:"
    echo "    source \$HOME/.cargo/env"
    echo ""
    echo "그 다음 이 스크립트를 다시 실행하세요."
    exit 0
fi

# 가상환경 생성
if [ ! -d .venv ]; then
    echo "가상환경을 생성합니다..."
    uv venv
else
    echo "가상환경이 이미 존재합니다."
fi

# Python 패키지 설치
echo ""
echo "Python 패키지를 설치합니다..."
source .venv/bin/activate
uv pip install discord.py python-dotenv arxiv openai pydantic requests

# 디렉토리 생성
echo ""
echo "필요한 디렉토리를 생성합니다..."
mkdir -p data/pending data/completed logs

# .env 파일 확인
if [ ! -f .env ]; then
    echo ""
    echo ".env 파일을 생성합니다..."
    cat > .env << 'EOL'
# Discord 설정
DISCORD_TOKEN=

# 카테고리별 채널 ID (Discord에서 채널 우클릭 -> ID 복사)
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
EOL
    echo ".env 파일이 생성되었습니다!"
else
    echo ""
    echo ".env 파일이 이미 존재합니다."
fi

echo ""
echo "========================================"
echo "설치가 완료되었습니다!"
echo "========================================"
echo ""
echo "다음 단계:"
echo "1. .env 파일을 열어서 DISCORD_TOKEN과 채널 ID를 설정하세요"
echo "2. vLLM 서버가 실행 중인지 확인하세요"
echo "3. 'bash run.sh --date YYYY-MM-DD'로 봇을 실행하세요"
echo "   예: bash run.sh --date 2025-11-22"
echo ""
