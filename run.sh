#!/bin/bash
# 봇 실행 스크립트

# 가상환경 활성화
if [ -d .venv ]; then
    source .venv/bin/activate
else
    echo "오류: 가상환경이 없습니다. 먼저 'bash setup.sh'를 실행하세요."
    exit 1
fi

# 인자 확인
if [ $# -eq 0 ]; then
    echo "사용법: bash run.sh --date YYYY-MM-DD"
    echo "예: bash run.sh --date 2025-11-22"
    exit 1
fi

# 봇 실행
echo "봇을 시작합니다..."
python bot.py "$@"
