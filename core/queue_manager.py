"""파일 기반 큐 관리 시스템"""
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime
import logging

from models.paper import Paper
from models.analysis import Analysis


class QueueManager:
    """파일 기반 논문 처리 큐 관리자"""
    
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.pending_dir = self.data_dir / 'pending'
        self.processing_file = self.data_dir / 'processing.json'
        self.completed_dir = self.data_dir / 'completed'
        self.logger = logging.getLogger('QueueManager')
        
        # 디렉토리 생성
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)
    
    def add_pending(self, paper: Paper) -> bool:
        """대기 큐에 논문 추가"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{paper.arxiv_id}.json"
            filepath = self.pending_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(paper.to_dict(), f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"pending 추가 실패: {e}")
            return False
    
    def get_next_pending(self) -> Optional[Paper]:
        """시간순으로 다음 처리할 논문 가져오기"""
        files = sorted(self.pending_dir.glob('*.json'))
        if not files:
            return None
        
        try:
            with open(files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Paper.from_dict(data)
        except Exception as e:
            self.logger.error(f"pending 읽기 실패: {e}")
            # 손상된 파일 삭제
            files[0].unlink()
            return None
    
    def start_processing(self, paper: Paper):
        """현재 처리 중인 논문 기록"""
        try:
            with open(self.processing_file, 'w', encoding='utf-8') as f:
                json.dump(paper.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"processing 기록 실패: {e}")
    
    def complete_processing(self, paper: Paper, analysis: Analysis):
        """논문 처리 완료: completed에 저장, pending/processing 삭제"""
        try:
            # completed 파일에 추가
            date_str = paper.published.strftime('%Y-%m-%d')
            completed_file = self.completed_dir / f"{date_str}.json"
            
            completed_data = []
            if completed_file.exists():
                with open(completed_file, 'r', encoding='utf-8') as f:
                    completed_data = json.load(f)
            
            completed_data.append({
                **paper.to_dict(),
                'llm_analysis': analysis.dict(),
                'processed_at': datetime.now().isoformat(),
                'discord_sent': True
            })
            
            with open(completed_file, 'w', encoding='utf-8') as f:
                json.dump(completed_data, f, ensure_ascii=False, indent=2)
            
            # pending 파일 삭제
            for f in self.pending_dir.glob(f"*_{paper.arxiv_id}.json"):
                f.unlink()
            
            # processing.json 삭제
            if self.processing_file.exists():
                self.processing_file.unlink()
            
            self.logger.info(f"완료 저장: {paper.arxiv_id}")
        except Exception as e:
            self.logger.error(f"complete 처리 실패: {e}")
    
    def is_duplicate(self, arxiv_id: str, published_date: str) -> bool:
        """중복 체크: 해당 날짜의 completed 파일 확인"""
        completed_file = self.completed_dir / f"{published_date}.json"
        if not completed_file.exists():
            return False
        
        try:
            with open(completed_file, 'r', encoding='utf-8') as f:
                completed = json.load(f)
            return any(p['arxiv_id'] == arxiv_id for p in completed)
        except Exception as e:
            self.logger.error(f"중복 체크 실패: {e}")
            return False
    
    def get_pending_count(self) -> int:
        """대기 큐 크기"""
        return len(list(self.pending_dir.glob('*.json')))
    
    def is_pending_empty(self) -> bool:
        """대기 큐가 비어있는지 확인"""
        return self.get_pending_count() == 0
    
    def restore_processing_to_pending(self):
        """재시작 시 processing → pending 복구"""
        if self.processing_file.exists():
            try:
                with open(self.processing_file, 'r', encoding='utf-8') as f:
                    paper_data = json.load(f)
                paper = Paper.from_dict(paper_data)
                self.add_pending(paper)
                self.processing_file.unlink()
                self.logger.info(f"processing 복구: {paper.arxiv_id}")
            except Exception as e:
                self.logger.error(f"processing 복구 실패: {e}")
    
    def get_today_completed_count(self) -> int:
        """오늘 처리한 논문 수"""
        today = datetime.now().strftime('%Y-%m-%d')
        completed_file = self.completed_dir / f"{today}.json"
        
        if not completed_file.exists():
            return 0
        
        try:
            with open(completed_file, 'r', encoding='utf-8') as f:
                completed = json.load(f)
            return len(completed)
        except:
            return 0

