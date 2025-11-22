#!/bin/bash
set -e

uv sync --extra dev

uv run ruff check --fix .
echo "✓ 린트 체크 완료"

uv run ruff format .
echo "✓ 포맷팅 완료"

uv run ruff check .
echo "✓ 최종 체크 완료"
