"""설정 파일 - 환경 변수 로드"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Discord 봇 토큰
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 카테고리별 채널 ID 매핑
CHANNEL_MAPPING = {}
for category in ['CS_AI', 'CS_LG', 'CS_CV', 'CS_CL', 'CS_NE', 'CS_CR']:
    channel_id = os.getenv(f'CHANNEL_{category}')
    if channel_id:
        # CS_AI -> cs.AI 형식으로 변환
        parts = category.split('_')  # ['CS', 'AI']
        category_key = f'{parts[0].lower()}.{parts[1]}'  # cs.AI
        CHANNEL_MAPPING[category_key] = int(channel_id)

# arXiv 설정
ARXIV_CATEGORIES = ['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'cs.NE', 'cs.CR']

# vLLM 설정
VLLM_BASE_URL = os.getenv('VLLM_BASE_URL', 'http://localhost:8000/v1')
VLLM_MODEL = os.getenv('VLLM_MODEL', '/models/gpt-oss-120b')
VLLM_MAX_TOKENS = int(os.getenv('VLLM_MAX_TOKENS', '1000'))
VLLM_TEMPERATURE = float(os.getenv('VLLM_TEMPERATURE', '0.0'))
VLLM_TIMEOUT = int(os.getenv('VLLM_TIMEOUT', '120'))
VLLM_MAX_RETRIES = int(os.getenv('VLLM_MAX_RETRIES', '3'))


def validate_config():
    """설정 검증"""
    if not DISCORD_TOKEN:
        print('오류: .env 파일에 DISCORD_TOKEN을 설정해주세요!')
        sys.exit(1)

    if not CHANNEL_MAPPING:
        print('경고: 채널 매핑이 설정되지 않았습니다. .env 파일을 확인하세요.')
        sys.exit(1)
