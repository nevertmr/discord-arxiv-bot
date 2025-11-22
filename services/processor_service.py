"""논문 처리 서비스"""
import logging
import asyncio
from typing import Optional

from clients.vllm_client import VLLMClient
from clients.discord_client import DiscordClient
from core.queue_manager import QueueManager
from models.paper import Paper
from config import CHANNEL_MAPPING


class ProcessorService:
    """큐에서 논문을 가져와 vLLM으로 분석하고 Discord에 발송하는 서비스"""
    
    def __init__(
        self,
        vllm_client: VLLMClient,
        discord_client: DiscordClient,
        queue_manager: QueueManager,
        max_retries: int = 3,
        consecutive_failure_limit: int = 3
    ):
        self.vllm_client = vllm_client
        self.discord_client = discord_client
        self.queue_manager = queue_manager
        self.max_retries = max_retries
        self.consecutive_failure_limit = consecutive_failure_limit
        self.logger = logging.getLogger('ProcessorService')
        
        self.consecutive_failures = 0
        self.is_running = False
    
    async def process_queue(self):
        """큐를 계속 처리하는 메인 루프"""
        self.is_running = True
        self.consecutive_failures = 0
        
        self.logger.info("Processor 시작")
        
        while self.is_running:
            try:
                # 다음 논문 가져오기
                paper = self.queue_manager.get_next_pending()
                
                if not paper:
                    # 큐가 비어있으면 대기
                    await asyncio.sleep(5)
                    continue
                
                # 처리 시작
                success = await self._process_single_paper(paper)
                
                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    
                    if self.consecutive_failures >= self.consecutive_failure_limit:
                        self.logger.critical(
                            f"{self.consecutive_failure_limit}개 논문 연속 실패 - Processor 종료"
                        )
                        print(f"\n❌ {self.consecutive_failure_limit}개 논문 연속 실패")
                        print("vLLM 서버에 문제가 있을 수 있습니다. 봇을 종료합니다.\n")
                        raise RuntimeError("연속 실패 제한 초과")
                
                # 다음 논문 처리 전 짧은 대기
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                self.logger.info("Processor 취소됨")
                break
            except Exception as e:
                self.logger.error(f"Processor 에러: {e}")
                raise
    
    async def _process_single_paper(self, paper: Paper) -> bool:
        """단일 논문 처리"""
        # Primary 카테고리가 설정된 채널 중 하나인지 확인
        if paper.primary_category not in CHANNEL_MAPPING:
            self.logger.info(f"카테고리 무시: {paper.primary_category} - {paper.arxiv_id}")
            # pending에서 제거
            for f in self.queue_manager.pending_dir.glob(f"*_{paper.arxiv_id}.json"):
                f.unlink()
            return True
        
        # 오늘 몇 번째 논문인지 확인
        today_count = self.queue_manager.get_today_completed_count() + 1
        
        self.logger.info(f"처리 시작 [{today_count}번째]: {paper.arxiv_id} ({paper.primary_category})")
        print(f"\n{'='*80}")
        print(f"📄 오늘 {today_count}번째 논문 처리 중")
        print(f"{'='*80}")
        print(f"ID: {paper.arxiv_id}")
        print(f"제목: {paper.title}")
        print(f"카테고리: {paper.primary_category}")
        print(f"{'='*80}\n")
        
        # processing으로 표시
        self.queue_manager.start_processing(paper)
        
        # vLLM으로 분석 (재시도 로직)
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(f"vLLM 시도 {attempt}/{self.max_retries}")
                analysis = self.vllm_client.analyze_paper(paper)
                
                # Discord 발송
                success = await self.discord_client.send_paper_notification(paper, analysis)
                
                if success:
                    # 완료 처리
                    self.queue_manager.complete_processing(paper, analysis)
                    self.logger.info(f"처리 완료 [{today_count}번째]: {paper.arxiv_id}")
                    return True
                else:
                    self.logger.warning(f"Discord 발송 실패: {paper.arxiv_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"vLLM 에러 (시도 {attempt}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries:
                    self.logger.info(f"재시도 대기 중... (5초)")
                    await asyncio.sleep(5)
                else:
                    self.logger.error(f"논문 처리 실패 (최대 재시도 초과): {paper.arxiv_id}")
                    # processing → pending 복구
                    self.queue_manager.restore_processing_to_pending()
                    return False
        
        return False
    
    def stop(self):
        """Processor 중지"""
        self.is_running = False
        self.logger.info("Processor 중지 요청됨")

