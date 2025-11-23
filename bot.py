"""
arXiv 논문 자동 알림 Discord 봇 (일회성 실행)
- 특정 날짜의 arXiv 논문 수집
- HTML 전문 다운로드
- vLLM으로 논문 분석
- Discord 채널별 자동 발송
"""

import argparse
import logging
import sys
from datetime import datetime

import discord
from discord.ext import commands

import config
from clients.arxiv_client import ArxivClient
from clients.discord_client import DiscordClient
from clients.vllm_client import VLLMClient
from core.queue_manager import QueueManager
from services.fetcher_service import FetcherService
from services.processor_service import ProcessorService
from utils.logger import setup_logger


def parse_arguments():
    """커맨드 라인 인자 파싱"""
    parser = argparse.ArgumentParser(description='arXiv 논문 자동 알림 Discord 봇')
    parser.add_argument('--date', type=str, required=True, help='처리할 날짜 (YYYY-MM-DD)')
    args = parser.parse_args()

    # 날짜 검증
    try:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        return target_date, args.date
    except ValueError:
        print('오류: 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요. (예: 2025-11-22)')
        sys.exit(1)


def create_bot(target_date, date_str):
    """Discord 봇 생성 및 초기화"""
    # 로깅 설정
    setup_logger(log_level=logging.INFO)
    logger = logging.getLogger('Bot')

    # Discord 봇 설정
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    # 모듈 초기화
    queue_manager = QueueManager(data_dir='data')

    arxiv_client = ArxivClient(categories=config.ARXIV_CATEGORIES)
    vllm_client = VLLMClient(
        base_url=config.VLLM_BASE_URL,
        model=config.VLLM_MODEL,
        max_tokens=config.VLLM_MAX_TOKENS,
        temperature=config.VLLM_TEMPERATURE,
        timeout=config.VLLM_TIMEOUT,
    )
    discord_client = DiscordClient(bot=bot, channel_mapping=config.CHANNEL_MAPPING)

    fetcher_service = FetcherService(arxiv_client=arxiv_client, queue_manager=queue_manager)
    processor_service = ProcessorService(
        vllm_client=vllm_client,
        discord_client=discord_client,
        queue_manager=queue_manager,
        max_retries=config.VLLM_MAX_RETRIES,
    )

    @bot.event
    async def on_ready():
        """봇이 준비되면 실행"""
        logger.info(f'봇 로그인: {bot.user.name} (ID: {bot.user.id})')

        print(f'\n{"=" * 80}')
        print('=== arXiv Discord Notifier ===')
        print(f'날짜: {date_str}')
        print(f'봇: {bot.user.name}')
        print(f'{"=" * 80}\n')

        try:
            # 1. Fetch: arXiv에서 논문 가져오기 (이미 있으면 스킵)
            pending_count = queue_manager.get_pending_count(date_str)
            if pending_count == 0:
                logger.info(f'{date_str}: pending 큐가 비어있음 - Fetch 시작')
                added_count = await fetcher_service.fetch_and_enqueue_for_date(target_date, date_str)

                if added_count == 0:
                    print(f'\n{"=" * 80}')
                    print(f'{date_str}: 처리할 논문이 없습니다.')
                    print(f'{"=" * 80}\n')
                    await bot.close()
                    return
            else:
                logger.info(f'{date_str}: pending에 {pending_count}개 논문 존재 - Fetch 스킵')
                print(f'\n{"=" * 80}')
                print(f'[QUEUE] pending에 {pending_count}개 논문 존재 (Fetch 스킵)')
                print(f'{"=" * 80}\n')

            # 2. Process: vLLM 분석 및 Discord 발송
            await processor_service.process_all_for_date(date_str)

            # 3. Stats: 통계 생성
            stats = queue_manager.generate_stats(date_str)
            logger.info(f'통계 생성: {stats}')

            print(f'\n{"=" * 80}')
            print('[통계]')
            for category, count in sorted(stats.items()):
                print(f'  {category}: {count}')
            print(f'{"=" * 80}\n')

            logger.info('모든 작업 완료')

        except Exception as e:
            logger.error(f'작업 실패: {e}', exc_info=True)
            print(f'\n❌ 오류 발생: {e}\n')
        finally:
            # 봇 종료
            await bot.close()

    return bot


def main():
    """메인 실행"""
    # 설정 검증
    config.validate_config()

    # 인자 파싱
    target_date, date_str = parse_arguments()

    # 봇 생성 및 실행
    bot = create_bot(target_date, date_str)

    try:
        bot.run(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logging.getLogger('Bot').info('KeyboardInterrupt 감지')
    except Exception as e:
        logging.getLogger('Bot').error(f'봇 실행 에러: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
