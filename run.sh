#!/bin/bash
# 봇 실행 스크립트

# 가상환경 활성화
if [ -d .venv ]; then
    source .venv/bin/activate
    echo "가상환경 활성화됨"
else
    echo "경고: 가상환경이 없습니다. 먼저 'uv venv'를 실행하세요."
    exit 1
fi

# 봇 실행
echo "봇을 시작합니다..."
python bot.py
