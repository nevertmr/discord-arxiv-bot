"""파일 기반 큐 관리 시스템 (날짜별)"""

import json
import logging
from datetime import datetime
from pathlib import Path

from models.analysis import Analysis
from models.paper import Paper


class QueueManager:
    """파일 기반 논문 처리 큐 관리자 (날짜별 폴더)"""

    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.pending_dir = self.data_dir / 'pending'
        self.completed_dir = self.data_dir / 'completed'
        self.logger = logging.getLogger('QueueManager')

        # 디렉토리 생성
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)

    def _get_date_dir(self, base_dir: Path, date_str: str) -> Path:
        """날짜별 디렉토리 경로"""
        date_dir = base_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    def add_pending(self, paper: Paper, date_str: str) -> bool:
        """대기 큐에 논문 메타데이터 추가"""
        try:
            date_dir = self._get_date_dir(self.pending_dir, date_str)

            # 메타데이터만 저장 (HTML은 처리 시 다운로드)
            json_file = date_dir / f'{paper.arxiv_id}.json'
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(paper.to_dict(), f, ensure_ascii=False, indent=2)

            self.logger.info(f'pending 추가: {paper.arxiv_id}')
            return True
        except Exception as e:
            self.logger.error(f'pending 추가 실패: {e}')
            return False

    def get_pending_papers(self, date_str: str) -> list[Paper]:
        """해당 날짜의 대기 중인 논문 목록 (메타데이터만)"""
        date_dir = self._get_date_dir(self.pending_dir, date_str)
        papers = []

        for json_file in sorted(date_dir.glob('*.json')):
            try:
                # 메타데이터 읽기
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)
                paper = Paper.from_dict(data)
                papers.append(paper)
            except Exception as e:
                self.logger.error(f'pending 읽기 실패: {json_file.name}, {e}')
                continue

        return papers

    def complete_processing(self, paper: Paper, content: str, content_type: str, analysis: Analysis, date_str: str):
        """논문 처리 완료: completed에 저장, pending 삭제"""
        try:
            completed_date_dir = self._get_date_dir(self.completed_dir, date_str)

            # 메타데이터 + 분석 결과 저장
            json_file = completed_date_dir / f'{paper.arxiv_id}.json'
            completed_data = {
                **paper.to_dict(),
                'content_type': content_type,
                'llm_analysis': analysis.dict(),
                'processed_at': datetime.now().isoformat(),
                'discord_sent': True,
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(completed_data, f, ensure_ascii=False, indent=2)

            # 콘텐츠 저장 (HTML 원문 또는 Abstract)
            content_file = completed_date_dir / f'{paper.arxiv_id}.txt'
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # pending 파일 삭제
            pending_date_dir = self._get_date_dir(self.pending_dir, date_str)
            (pending_date_dir / f'{paper.arxiv_id}.json').unlink(missing_ok=True)

            self.logger.info(f'완료 저장: {paper.arxiv_id}')
        except Exception as e:
            self.logger.error(f'complete 처리 실패: {e}')
            raise

    def is_duplicate(self, arxiv_id: str, date_str: str) -> bool:
        """중복 체크: completed와 pending 확인"""
        # 1. completed 체크
        completed_date_dir = self.completed_dir / date_str
        if completed_date_dir.exists():
            if (completed_date_dir / f'{arxiv_id}.json').exists():
                return True

        # 2. pending 체크
        pending_date_dir = self.pending_dir / date_str
        if pending_date_dir.exists():
            if (pending_date_dir / f'{arxiv_id}.json').exists():
                return True

        return False

    def get_pending_count(self, date_str: str) -> int:
        """해당 날짜의 대기 큐 크기"""
        date_dir = self.pending_dir / date_str
        if not date_dir.exists():
            return 0
        return len(list(date_dir.glob('*.json')))

    def get_completed_count(self, date_str: str) -> int:
        """해당 날짜의 완료된 논문 수"""
        date_dir = self.completed_dir / date_str
        if not date_dir.exists():
            return 0
        return len(list(date_dir.glob('*.json')))

    def generate_stats(self, date_str: str) -> dict:
        """해당 날짜의 통계 생성"""
        completed_date_dir = self.completed_dir / date_str
        if not completed_date_dir.exists():
            return {}

        stats = {}
        for json_file in completed_date_dir.glob('*.json'):
            try:
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)
                primary_cat = data.get('primary_category', 'unknown')
                stats[primary_cat] = stats.get(primary_cat, 0) + 1
            except Exception as e:
                self.logger.error(f'통계 생성 실패: {json_file.name}, {e}')

        # 통계 파일 저장
        stats_file = completed_date_dir / 'stats.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        return stats
