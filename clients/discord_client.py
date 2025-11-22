"""Discord API 클라이언트"""

import logging

import discord

from models.analysis import Analysis
from models.paper import Paper


class DiscordClient:
    """Discord 발송 래퍼"""

    def __init__(self, bot, channel_mapping: dict[str, int]):
        self.bot = bot
        self.channel_mapping = channel_mapping
        self.logger = logging.getLogger('DiscordClient')

        # 카테고리별 색상
        self.colors = {
            'cs.AI': 0xE74C3C,  # 빨간색
            'cs.LG': 0x3498DB,  # 파란색
            'cs.CV': 0x2ECC71,  # 초록색
            'cs.CL': 0x9B59B6,  # 보라색
            'cs.NE': 0xF39C12,  # 주황색
            'cs.CR': 0xE67E22,  # 진한 주황색 (Cryptography)
        }

    async def send_paper_notification(self, paper: Paper, analysis: Analysis) -> bool:
        """논문 알림 발송"""
        # 발송할 카테고리 결정: primary 우선, 없으면 secondary 확인
        target_category = self._determine_target_category(paper)

        if not target_category:
            self.logger.warning(
                f"발송 불가: primary '{paper.primary_category}' 및 secondary {paper.all_categories} 모두 채널 설정 없음"
            )
            return False

        channel_id = self.channel_mapping.get(target_category)
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.logger.error(f'채널을 찾을 수 없음: {channel_id} ({target_category})')
            return False

        # Embed 생성 시 실제 발송 카테고리 사용
        embed = self._create_embed(paper, analysis, target_category)

        try:
            await channel.send(embed=embed)
            if target_category != paper.primary_category:
                self.logger.info(
                    f'Discord 발송 완료: {target_category} 채널 '
                    f"(primary '{paper.primary_category}'가 아닌 secondary 사용)"
                )
                print(f'✅ Discord 발송 완료: {target_category} 채널 (secondary 사용)\n')
            else:
                self.logger.info(f'Discord 발송 완료: {target_category} 채널')
                print(f'✅ Discord 발송 완료: {target_category} 채널\n')
            return True
        except Exception as e:
            self.logger.error(f'Discord 발송 실패: {e}')
            return False

    def _determine_target_category(self, paper: Paper) -> str:
        """발송할 카테고리 결정: primary 우선, 없으면 secondary 확인"""
        # 1. Primary 카테고리가 채널 목록에 있는지 확인
        if paper.primary_category in self.channel_mapping:
            return paper.primary_category

        # 2. Primary가 없으면 all_categories에서 첫 번째 매칭되는 카테고리 찾기
        for category in paper.all_categories:
            if category in self.channel_mapping:
                return category

        # 3. 매칭되는 카테고리가 없음
        return None

    def _create_embed(self, paper: Paper, analysis: Analysis, target_category: str = None) -> discord.Embed:
        """Discord Embed 생성"""
        # 표시할 카테고리 (발송 카테고리 또는 primary)
        display_category = target_category or paper.primary_category

        embed = discord.Embed(
            title=f'📄 {paper.title}',
            url=paper.url,
            color=self.colors.get(display_category, 0x95A5A6),
            timestamp=paper.published,
        )

        # 저자
        authors_text = ', '.join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors_text += f' 외 {len(paper.authors) - 5}명'
        embed.add_field(name='저자', value=authors_text, inline=False)

        # 카테고리 및 발행일
        # primary와 실제 발송 카테고리가 다르면 둘 다 표시
        if display_category != paper.primary_category:
            category_text = f'{display_category} (primary: {paper.primary_category})'
        else:
            category_text = paper.primary_category
        embed.add_field(name='카테고리', value=category_text, inline=True)
        embed.add_field(name='발행일', value=paper.published.strftime('%Y-%m-%d'), inline=True)

        # AI 분석 결과
        analysis_text = f'**요약**\n{analysis.summary}\n\n'
        analysis_text += f'**기술/방법론**\n{analysis.methodology}\n\n'
        analysis_text += f'**연구 맥락**\n{analysis.context}\n\n'
        analysis_text += f'**기여**\n{analysis.contribution}'

        # 2000자 제한 체크
        if len(analysis_text) > 1024:
            analysis_text = analysis_text[:1020] + '...'

        embed.add_field(name='AI 분석', value=analysis_text, inline=False)

        # 링크
        links = f'[arXiv]({paper.url}) | [PDF]({paper.pdf_url})'
        embed.add_field(name='링크', value=links, inline=False)

        return embed
