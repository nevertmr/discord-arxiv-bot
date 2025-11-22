"""
arXiv 논문 자동 알림 Discord 봇
- arXiv에서 최신 논문 자동 수집
- vLLM으로 논문 분석
- Discord 채널별 자동 발송
"""
import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime

import config
from utils.logger import setup_logger
from utils.stats import StatsGenerator
from core.queue_manager import QueueManager
from clients.arxiv_client import ArxivClient
from clients.vllm_client import VLLMClient
from clients.discord_client import DiscordClient
from services.fetcher_service import FetcherService
from services.processor_service import ProcessorService


# 로깅 설정
setup_logger(log_level=logging.INFO)
logger = logging.getLogger('Bot')

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 모듈 초기화
queue_manager = QueueManager(data_dir='data')
stats_generator = StatsGenerator(completed_dir='data/completed')

arxiv_client = ArxivClient(categories=config.ARXIV_CATEGORIES)
vllm_client = VLLMClient(
    base_url=config.VLLM_BASE_URL,
    model=config.VLLM_MODEL,
    max_tokens=config.VLLM_MAX_TOKENS,
    temperature=config.VLLM_TEMPERATURE,
    timeout=config.VLLM_TIMEOUT
)
discord_client = DiscordClient(bot=bot, channel_mapping=config.CHANNEL_MAPPING)

fetcher_service = FetcherService(arxiv_client=arxiv_client, queue_manager=queue_manager)
processor_service = ProcessorService(
    vllm_client=vllm_client,
    discord_client=discord_client,
    queue_manager=queue_manager,
    max_retries=config.VLLM_MAX_RETRIES,
    consecutive_failure_limit=config.VLLM_CONSECUTIVE_FAILURE_LIMIT
)

# 전역 태스크
processor_task = None


@bot.event
async def on_ready():
    """봇이 준비되면 실행"""
    logger.info(f'봇 로그인: {bot.user.name} (ID: {bot.user.id})')
    print(f"\n{'='*80}")
    print(f"봇 시작됨: {bot.user.name}")
    print(f"{'='*80}\n")
    
    # Processing 복구
    queue_manager.restore_processing_to_pending()
    
    # 어제 통계 생성 (아직 안 했으면)
    stats_generator.check_and_generate_yesterday_stats()
    
    # 초기 실행 확인
    if queue_manager.is_pending_empty():
        logger.info(f"초기 실행 감지 - {config.INITIAL_FETCH_COUNT}개 논문 가져오기")
        print(f"\n{'='*80}")
        print(f"초기 실행: {config.INITIAL_FETCH_COUNT}개 논문을 가져옵니다...")
        print(f"{'='*80}\n")
        await fetcher_service.fetch_and_enqueue(
            max_results=config.INITIAL_FETCH_COUNT,
            is_initial=True
        )
    else:
        pending_count = queue_manager.get_pending_count()
        logger.info(f"대기 큐: {pending_count}개 논문")
        print(f"대기 큐: {pending_count}개 논문\n")
    
    # 태스크 시작
    fetch_papers_task.start()
    
    # Processor를 별도 태스크로 실행
    global processor_task
    processor_task = asyncio.create_task(processor_service.process_queue())


@tasks.loop(minutes=config.CHECK_INTERVAL_MINUTES)
async def fetch_papers_task():
    """주기적으로 arXiv에서 새 논문 가져오기"""
    try:
        logger.info("정기 Fetch 시작")
        await fetcher_service.fetch_and_enqueue(max_results=config.INITIAL_FETCH_COUNT)
    except Exception as e:
        logger.error(f"Fetch 태스크 에러: {e}")


@fetch_papers_task.before_loop
async def before_fetch():
    """Fetch 태스크 시작 전 봇이 준비될 때까지 대기"""
    await bot.wait_until_ready()


@bot.event
async def on_command_error(ctx, error):
    """명령어 에러 처리"""
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error(f"명령어 에러: {error}")


async def shutdown():
    """봇 종료 처리"""
    logger.info("봇 종료 중...")
    
    # 태스크 중지
    if fetch_papers_task.is_running():
        fetch_papers_task.cancel()
    
    processor_service.stop()
    
    if processor_task:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
    
    await bot.close()
    logger.info("봇 종료 완료")


def main():
    """메인 실행"""
    if not config.DISCORD_TOKEN:
        print("오류: .env 파일에 DISCORD_TOKEN을 설정해주세요!")
        return
    
    if not config.CHANNEL_MAPPING:
        print("경고: 채널 매핑이 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    try:
        bot.run(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt 감지")
    except Exception as e:
        logger.error(f"봇 실행 에러: {e}")
    finally:
        # 정리 작업
        pass


if __name__ == '__main__':
    main()
