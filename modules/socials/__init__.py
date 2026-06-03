"""
Lycan Bot - Socials Module
Twitch and YouTube notifications with professional styling.
Alerts when a streamer goes live or posts a new video.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
import aiohttp
import asyncio
from datetime import datetime
import logging

from .webhook_server import (
    set_discord_bot,
    subscribe_twitch_eventsub,
    subscribe_youtube_websub,
    start_webhook_server_async
)

logger = logging.getLogger("LYCAN.socials")


# Professional color palette
COLORS = {
    "twitch": 0x9146FF,       # Twitch purple
    "youtube": 0xFF0000,      # YouTube red
    "accent": 0x3498DB,       # Professional blue
    "success": 0x2ECC71,      # Success green
}

LYCAN_ICON = ""
LYCAN_FOOTER = "Lycan Notifications"


class SocialsCog(commands.Cog):
    """Social media notifications with professional embeds."""
    
    def __init__(self, bot):
        self.bot = bot
        self.twitch_token = None
        self.check_twitch.start()
        self.webhook_task = None
        
        # Start webhook server
        self._start_webhook_server()
    
    def _start_webhook_server(self):
        """Start webhook server in background."""
        set_discord_bot(self.bot)
        
        async def run_server():
            try:
                await start_webhook_server_async()
            except Exception as e:
                logger.error(f"Webhook server error: {e}")
        
        self.webhook_task = asyncio.create_task(run_server())
        logger.info("Webhook server starting on port 6100")
    
    def cog_unload(self):
        self.check_twitch.cancel()
    
    async def _get_twitch_token(self) -> Optional[str]:
        """Get Twitch API token."""
        if not self.bot.config.twitch_client_id or not self.bot.config.twitch_client_secret:
            return None
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": self.bot.config.twitch_client_id,
                    "client_secret": self.bot.config.twitch_client_secret,
                    "grant_type": "client_credentials"
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("access_token")
        return None
    
    def _create_twitch_embed(self, stream: dict, username: str) -> discord.Embed:
        """Create a professional Twitch live notification embed."""
        embed = discord.Embed(
            color=COLORS["twitch"],
            timestamp=datetime.utcnow()
        )
        
        # Title with live indicator
        embed.set_author(
            name=f"🔴 LIVE  •  {stream['user_name']}",
            url=f"https://twitch.tv/{username}",
            icon_url="https://static.twitchcdn.net/assets/favicon-32-e29e246c157142c94346.png"
        )
        
        # Stream title as main content
        embed.title = stream.get('title', 'Untitled Stream')
        embed.url = f"https://twitch.tv/{username}"
        
        # Stream info fields
        embed.add_field(
            name="🎮 Category",
            value=stream.get('game_name', 'Just Chatting'),
            inline=True
        )
        embed.add_field(
            name="👁️ Viewers",
            value=f"**{stream.get('viewer_count', 0):,}**",
            inline=True
        )
        embed.add_field(
            name="⏱️ Started",
            value=f"<t:{int(datetime.fromisoformat(stream.get('started_at', '').replace('Z', '+00:00')).timestamp())}:R>" if stream.get('started_at') else "Just now",
            inline=True
        )
        
        # Thumbnail
        thumbnail = stream.get('thumbnail_url', '').replace('{width}', '1280').replace('{height}', '720')
        if thumbnail:
            embed.set_image(url=thumbnail + f"?t={int(datetime.utcnow().timestamp())}")
        
        embed.set_footer(text=f"{LYCAN_FOOTER} • Twitch", icon_url="https://static.twitchcdn.net/assets/favicon-32-e29e246c157142c94346.png")
        
        return embed
    
    def _create_youtube_embed(self, video_title: str, channel_name: str, video_url: str) -> discord.Embed:
        """Create a professional YouTube notification embed."""
        embed = discord.Embed(
            color=COLORS["youtube"],
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=f"📺 New Upload  •  {channel_name}",
            url=video_url,
            icon_url="https://www.youtube.com/s/desktop/fe666a06/img/favicon_144x144.png"
        )
        
        embed.title = video_title
        embed.url = video_url
        
        embed.set_footer(text=f"{LYCAN_FOOTER} • YouTube")
        
        return embed
    
    @tasks.loop(minutes=5)
    async def check_twitch(self):
        """Check Twitch streams every 5 minutes."""
        if not self.twitch_token:
            self.twitch_token = await self._get_twitch_token()
            if not self.twitch_token:
                return
        
        feeds = await self.bot.db.fetch(
            "SELECT * FROM social_feeds WHERE platform = 'twitch'"
        )
        
        if not feeds:
            return
        
        async with aiohttp.ClientSession() as session:
            for feed in feeds:
                await self._check_twitch_stream(session, dict(feed))
    
    @check_twitch.before_loop
    async def before_check_twitch(self):
        await self.bot.wait_until_ready()
    
    async def _check_twitch_stream(self, session: aiohttp.ClientSession, feed: dict) -> None:
        """Check if a streamer is live."""
        headers = {
            "Client-ID": self.bot.config.twitch_client_id,
            "Authorization": f"Bearer {self.twitch_token}"
        }
        
        async with session.get(
            f"https://api.twitch.tv/helix/streams?user_login={feed['channel_id']}",
            headers=headers
        ) as resp:
            if resp.status != 200:
                return
            
            data = await resp.json()
            streams = data.get("data", [])
            
            if streams:
                stream = streams[0]
                
                # Check if we already notified for this stream
                last = feed.get('last_notified_at')
                if last and (datetime.utcnow() - last).seconds < 3600:  # 1 hour cooldown
                    return
                
                # Send notification
                guild = self.bot.get_guild(feed['guild_id'])
                if not guild:
                    return
                
                channel = guild.get_channel(feed['discord_channel_id'])
                if not channel:
                    return
                
                embed = self._create_twitch_embed(stream, feed['channel_id'])
                custom_msg = feed.get('custom_message', '')
                await channel.send(content=custom_msg, embed=embed)
                
                # Update last_notified
                await self.bot.db.execute(
                    "UPDATE social_feeds SET last_notified_at = NOW() WHERE id = $1",
                    feed['id']
                )
    
    socials_group = app_commands.Group(
        name="socials",
        description="Social media notifications for Twitch and YouTube"
    )
    
    @socials_group.command(
        name="add_twitch",
        description="Add Twitch stream notifications"
    )
    @app_commands.describe(
        username="The Twitch username to monitor",
        channel="The Discord channel for notifications",
        message="Optional custom message to include with the notification"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_twitch(self, interaction: discord.Interaction, username: str, channel: discord.TextChannel, message: str = None):
        """Add a Twitch streamer for notifications."""
        await self.bot.db.execute(
            """
            INSERT INTO social_feeds (guild_id, platform, channel_id, discord_channel_id, custom_message)
            VALUES ($1, 'twitch', $2, $3, $4)
            ON CONFLICT (guild_id, platform, channel_id) DO UPDATE SET 
                discord_channel_id = EXCLUDED.discord_channel_id,
                custom_message = EXCLUDED.custom_message
            """,
            interaction.guild_id, username.lower(), channel.id, 
            message or f"@everyone {username} is streaming, come to see it!"
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Twitch Feed Added",
            color=COLORS["twitch"]
        )
        embed.add_field(name="Streamer", value=f"**{username}**", inline=True)
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Subscribe to EventSub
        asyncio.create_task(subscribe_twitch_eventsub(username.lower()))
    
    @socials_group.command(
        name="add_youtube",
        description="Add YouTube channel notifications"
    )
    @app_commands.describe(
        channel_id="The YouTube channel ID (not the @handle)",
        channel="The Discord channel for notifications",
        message="Optional custom message to include with the notification"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_youtube(self, interaction: discord.Interaction, channel_id: str, channel: discord.TextChannel, message: str = None):
        """Add a YouTube channel for notifications."""
        await self.bot.db.execute(
            """
            INSERT INTO social_feeds (guild_id, platform, channel_id, discord_channel_id, custom_message)
            VALUES ($1, 'youtube', $2, $3, $4)
            ON CONFLICT (guild_id, platform, channel_id) DO UPDATE SET 
                discord_channel_id = EXCLUDED.discord_channel_id,
                custom_message = EXCLUDED.custom_message
            """,
            interaction.guild_id, channel_id, channel.id, message
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} YouTube Feed Added",
            color=COLORS["youtube"]
        )
        embed.add_field(name="Channel ID", value=f"**{channel_id}**", inline=True)
        embed.add_field(name="Notifications", value=channel.mention, inline=True)
        embed.add_field(
            name="⚠️ Note",
            value="YouTube requires PubSubHubbub setup (coming soon)",
            inline=False
        )
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Subscribe to WebSub
        asyncio.create_task(subscribe_youtube_websub(channel_id))
    
    @socials_group.command(
        name="list",
        description="List all configured notifications"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_socials(self, interaction: discord.Interaction):
        """List all configured notifications."""
        feeds = await self.bot.db.fetch(
            "SELECT * FROM social_feeds WHERE guild_id = $1",
            interaction.guild_id
        )
        
        if not feeds:
            embed = discord.Embed(
                title=f"{LYCAN_ICON} Social Feeds",
                description="No notifications configured yet.",
                color=COLORS["accent"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Social Feeds",
            color=COLORS["accent"],
            timestamp=datetime.utcnow()
        )
        
        twitch_feeds = []
        youtube_feeds = []
        
        for feed in feeds:
            channel = interaction.guild.get_channel(feed['discord_channel_id'])
            channel_text = channel.mention if channel else "*deleted*"
            
            if feed['platform'] == 'twitch':
                twitch_feeds.append(f"**{feed['channel_id']}** → {channel_text}")
            else:
                youtube_feeds.append(f"**{feed['channel_id']}** → {channel_text}")
        
        if twitch_feeds:
            embed.add_field(
                name="🟣 Twitch",
                value="\n".join(twitch_feeds),
                inline=False
            )
        
        if youtube_feeds:
            embed.add_field(
                name="🔴 YouTube",
                value="\n".join(youtube_feeds),
                inline=False
            )
        
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @socials_group.command(
        name="remove",
        description="Remove a notification"
    )
    @app_commands.describe(
        platform="The platform (twitch or youtube)",
        channel_id="The channel ID or username to remove"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Twitch", value="twitch"),
        app_commands.Choice(name="YouTube", value="youtube")
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_social(self, interaction: discord.Interaction, platform: str, channel_id: str):
        """Remove a notification."""
        await self.bot.db.execute(
            "DELETE FROM social_feeds WHERE guild_id = $1 AND platform = $2 AND channel_id = $3",
            interaction.guild_id, platform.lower(), channel_id.lower()
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Feed Removed",
            description=f"Removed **{channel_id}** from {platform.title()} notifications.",
            color=COLORS["accent"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ==================== PREFIX COMMANDS (TESTING) ====================
    
    @commands.command(name="stest", hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def test_social(self, ctx: commands.Context, platform: str, channel_id: str):
        """Simulate a social notification (testing only)."""
        if platform.lower() == "twitch":
            # Create mock stream data
            mock_stream = {
                "user_name": channel_id,
                "title": "Test Stream - Professional Embed Demo",
                "game_name": "Just Chatting",
                "viewer_count": 1337,
                "started_at": datetime.utcnow().isoformat() + "Z",
                "thumbnail_url": ""
            }
            embed = self._create_twitch_embed(mock_stream, channel_id)
            await ctx.send(embed=embed)
        else:
            embed = self._create_youtube_embed(
                "Test Video - Professional Embed Demo",
                channel_id,
                f"https://youtube.com/@{channel_id}"
            )
            await ctx.send(embed=embed)
        
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(SocialsCog(bot))
