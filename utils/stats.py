"""일일 통계 생성"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


class StatsGenerator:
    """일일 통계 생성 및 관리"""

    def __init__(self, completed_dir: str = 'data/completed'):
        self.completed_dir = Path(completed_dir)
        self.logger = logging.getLogger('StatsGenerator')

    def generate_daily_stats(self, date_str: str):
        """특정 날짜의 통계 생성"""
        completed_file = self.completed_dir / f'{date_str}.json'

        if not completed_file.exists():
            self.logger.warning(f'완료 파일 없음: {date_str}')
            return

        try:
            with open(completed_file, encoding='utf-8') as f:
                papers = json.load(f)

            if not papers:
                return

            # 카테고리별 통계
            categories = [p['primary_category'] for p in papers]
            category_counts = dict(Counter(categories))

            stats = {
                'date': date_str,
                'total': len(papers),
                'by_category': category_counts,
                'generated_at': datetime.now().isoformat(),
            }

            self.logger.info(f'📊 {date_str} 통계: 총 {len(papers)}개 논문')
            print(f'\n{"=" * 80}')
            print(f'📊 {date_str} 일일 통계')
            print(f'{"=" * 80}')
            print(f'총 논문 수: {len(papers)}개')
            print('\n카테고리별:')
            for cat, count in sorted(category_counts.items()):
                print(f'  {cat}: {count}개')
            print(f'{"=" * 80}\n')

            # 통계를 completed 파일 상단에 메타데이터로 추가
            data_with_stats = {'stats': stats, 'papers': papers}

            with open(completed_file, 'w', encoding='utf-8') as f:
                json.dump(data_with_stats, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f'통계 생성 실패: {e}')

    def check_and_generate_yesterday_stats(self):
        """어제 날짜의 통계가 없으면 생성"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        completed_file = self.completed_dir / f'{yesterday}.json'

        if not completed_file.exists():
            return

        try:
            with open(completed_file, encoding='utf-8') as f:
                data = json.load(f)

            # 이미 통계가 있는지 확인 (stats 키가 있으면)
            if isinstance(data, dict) and 'stats' in data:
                return

            # 통계 생성
            self.generate_daily_stats(yesterday)

        except Exception as e:
            self.logger.error(f'어제 통계 확인 실패: {e}')
