"""Discord API 클라이언트"""
import discord
from typing import Dict
import logging

from models.paper import Paper
from models.analysis import Analysis


class DiscordClient:
    """Discord 발송 래퍼"""
    
    def __init__(self, bot, channel_mapping: Dict[str, int]):
        self.bot = bot
        self.channel_mapping = channel_mapping
        self.logger = logging.getLogger('DiscordClient')
        
        # 카테고리별 색상
        self.colors = {
            'cs.AI': 0xe74c3c,      # 빨간색
            'cs.LG': 0x3498db,      # 파란색
            'cs.CV': 0x2ecc71,      # 초록색
            'cs.CL': 0x9b59b6,      # 보라색
            'cs.NE': 0xf39c12,      # 주황색
            'cs.CR': 0xe67e22,      # 진한 주황색 (Cryptography)
        }
    
    async def send_paper_notification(self, paper: Paper, analysis: Analysis) -> bool:
        """논문 알림 발송"""
        category = paper.primary_category
        channel_id = self.channel_mapping.get(category)
        
        if not channel_id:
            self.logger.warning(f"채널 설정 없음: {category}")
            return False
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.logger.error(f"채널을 찾을 수 없음: {channel_id} ({category})")
            return False
        
        embed = self._create_embed(paper, analysis)
        
        try:
            await channel.send(embed=embed)
            self.logger.info(f"Discord 발송 완료: {category} 채널")
            print(f"✅ Discord 발송 완료: {category} 채널\n")
            return True
        except Exception as e:
            self.logger.error(f"Discord 발송 실패: {e}")
            return False
    
    def _create_embed(self, paper: Paper, analysis: Analysis) -> discord.Embed:
        """Discord Embed 생성"""
        embed = discord.Embed(
            title=f"📄 {paper.title}",
            url=paper.url,
            color=self.colors.get(paper.primary_category, 0x95a5a6),
            timestamp=paper.published
        )
        
        # 저자
        authors_text = ', '.join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors_text += f" 외 {len(paper.authors)-5}명"
        embed.add_field(name="저자", value=authors_text, inline=False)
        
        # 카테고리 및 발행일
        embed.add_field(name="카테고리", value=paper.primary_category, inline=True)
        embed.add_field(name="발행일", value=paper.published.strftime('%Y-%m-%d'), inline=True)
        
        # AI 분석 결과
        analysis_text = f"**요약**\n{analysis.summary}\n\n"
        analysis_text += f"**기술/방법론**\n{analysis.methodology}\n\n"
        analysis_text += f"**연구 맥락**\n{analysis.context}\n\n"
        analysis_text += f"**기여**\n{analysis.contribution}"
        
        # 2000자 제한 체크
        if len(analysis_text) > 1024:
            analysis_text = analysis_text[:1020] + "..."
        
        embed.add_field(name="AI 분석", value=analysis_text, inline=False)
        
        # 링크
        links = f"[arXiv]({paper.url}) | [PDF]({paper.pdf_url})"
        embed.add_field(name="링크", value=links, inline=False)
        
        return embed
    
    def _get_color(self, category: str) -> int:
        """카테고리별 색상"""
        return self.colors.get(category, 0x95a5a6)

