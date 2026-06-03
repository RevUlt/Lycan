"""
Lycan Bot - Welcome/Goodbye Module
Automatic messages when members join or leave the server.
Professional, elegant embeds with Lycan branding.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import random
from datetime import datetime


# Professional color palette
COLORS = {
    "welcome": 0x2ECC71,      # Emerald green
    "goodbye": 0x95A5A6,      # Silver gray
    "accent": 0x3498DB,       # Professional blue
    "warning": 0xE74C3C,      # Alert red
    "gold": 0xF1C40F,         # Premium gold
}

# Lycan branding
LYCAN_ICON = ""
LYCAN_FOOTER = "Lycan Security System"

# Professional welcome messages
WELCOME_MESSAGES = [
    "Welcome to **{server}**, {user}. You are member **#{member_count}**.",
    "A new member has joined our ranks. Welcome, {user}.",
    "{user} has entered the server. We are now **{member_count}** strong.",
    "Greetings, {user}. Welcome to **{server}**.",
    "The pack grows stronger. Welcome aboard, {user}.",
]

# Professional goodbye messages
GOODBYE_MESSAGES = [
    "**{user_name}** has left the server.",
    "Farewell, **{user_name}**. Until we meet again.",
    "**{user_name}** has departed from **{server}**.",
    "We bid goodbye to **{user_name}**.",
    "**{user_name}** is no longer with us.",
]


class WelcomeCog(commands.Cog):
    """Handles welcome and goodbye messages with professional styling."""
    
    def __init__(self, bot):
        self.bot = bot
    
    def _format_message(self, template: str, member: discord.Member) -> str:
        """Replace placeholders in the message template."""
        return template.format(
            user=member.mention,
            user_name=member.display_name,
            user_avatar=str(member.display_avatar.url),
            server=member.guild.name,
            member_count=member.guild.member_count
        )
    
    async def _get_config(self, guild_id: int) -> Optional[dict]:
        """Get welcome/goodbye config from database."""
        row = await self.bot.db.fetchrow(
            "SELECT * FROM guild_config WHERE guild_id = $1",
            guild_id
        )
        return dict(row) if row else None
    
    async def _ensure_config(self, guild_id: int) -> None:
        """Create config entry if it doesn't exist."""
        await self.bot.db.execute(
            """
            INSERT INTO guild_config (guild_id) 
            VALUES ($1) 
            ON CONFLICT (guild_id) DO NOTHING
            """,
            guild_id
        )
    
    def _create_welcome_embed(self, member: discord.Member, message: str) -> discord.Embed:
        """Create a professional welcome embed."""
        embed = discord.Embed(
            title=f"{LYCAN_ICON} New Member",
            color=COLORS["welcome"],
            timestamp=datetime.utcnow()
        )
        
        # Main content
        embed.add_field(
            name="Welcome",
            value=message,
            inline=False
        )
        
        # Member info section
        account_age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="Member Count",
            value=f"**{member.guild.member_count:,}**",
            inline=True
        )
        
        # Warning for new accounts
        if account_age < 7:
            embed.add_field(
                name="⚠️ Notice",
                value=f"Account is only **{account_age}** days old",
                inline=True
            )
        
        # Visual elements
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=LYCAN_FOOTER, icon_url=member.guild.icon.url if member.guild.icon else None)
        
        return embed
    
    def _create_goodbye_embed(self, member: discord.Member, message: str) -> discord.Embed:
        """Create a professional goodbye embed."""
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Member Left",
            color=COLORS["goodbye"],
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Farewell",
            value=message,
            inline=False
        )
        
        # Member info
        if member.joined_at:
            days_in_server = (datetime.utcnow() - member.joined_at.replace(tzinfo=None)).days
            embed.add_field(
                name="Time in Server",
                value=f"**{days_in_server}** days",
                inline=True
            )
        
        embed.add_field(
            name="Members Remaining",
            value=f"**{member.guild.member_count:,}**",
            inline=True
        )
        
        embed.set_footer(text=LYCAN_FOOTER, icon_url=member.guild.icon.url if member.guild.icon else None)
        
        return embed
    
    # ==================== EVENTS ====================
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send welcome message when a member joins."""
        config = await self._get_config(member.guild.id)
        if not config or not config.get('welcome_channel_id'):
            return
        
        channel = member.guild.get_channel(config['welcome_channel_id'])
        if not channel:
            return
        
        # Use custom message or random default
        message = config.get('welcome_message') or random.choice(WELCOME_MESSAGES)
        formatted = self._format_message(message, member)
        
        embed = self._create_welcome_embed(member, formatted)
        await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send goodbye message when a member leaves."""
        config = await self._get_config(member.guild.id)
        if not config or not config.get('goodbye_channel_id'):
            return
        
        channel = member.guild.get_channel(config['goodbye_channel_id'])
        if not channel:
            return
        
        message = config.get('goodbye_message') or random.choice(GOODBYE_MESSAGES)
        formatted = self._format_message(message, member)
        
        embed = self._create_goodbye_embed(member, formatted)
        await channel.send(embed=embed)
    
    # ==================== SLASH COMMANDS ====================
    
    welcome_group = app_commands.Group(
        name="welcome",
        description="Configure welcome messages for new members"
    )
    goodbye_group = app_commands.Group(
        name="goodbye", 
        description="Configure goodbye messages for leaving members"
    )
    
    @welcome_group.command(
        name="channel",
        description="Set the channel for welcome messages"
    )
    @app_commands.describe(
        channel="The text channel where welcome messages will be sent"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._ensure_config(interaction.guild_id)
        await self.bot.db.execute(
            "UPDATE guild_config SET welcome_channel_id = $1 WHERE guild_id = $2",
            channel.id, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Welcome Channel Set",
            description=f"Welcome messages will now be sent to {channel.mention}",
            color=COLORS["accent"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @welcome_group.command(
        name="message",
        description="Set a custom welcome message (or leave empty for random)"
    )
    @app_commands.describe(
        message="Custom message. Use {user}, {user_name}, {server}, {member_count} as placeholders"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_message(self, interaction: discord.Interaction, message: str):
        await self._ensure_config(interaction.guild_id)
        await self.bot.db.execute(
            "UPDATE guild_config SET welcome_message = $1 WHERE guild_id = $2",
            message, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Welcome Message Updated",
            description=f"```{message}```",
            color=COLORS["accent"]
        )
        embed.add_field(
            name="Placeholders",
            value="`{user}` `{user_name}` `{server}` `{member_count}`",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @goodbye_group.command(
        name="channel",
        description="Set the channel for goodbye messages"
    )
    @app_commands.describe(
        channel="The text channel where goodbye messages will be sent"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._ensure_config(interaction.guild_id)
        await self.bot.db.execute(
            "UPDATE guild_config SET goodbye_channel_id = $1 WHERE guild_id = $2",
            channel.id, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Goodbye Channel Set",
            description=f"Goodbye messages will now be sent to {channel.mention}",
            color=COLORS["accent"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @goodbye_group.command(
        name="message",
        description="Set a custom goodbye message (or leave empty for random)"
    )
    @app_commands.describe(
        message="Custom message. Use {user}, {user_name}, {server}, {member_count} as placeholders"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_message(self, interaction: discord.Interaction, message: str):
        await self._ensure_config(interaction.guild_id)
        await self.bot.db.execute(
            "UPDATE guild_config SET goodbye_message = $1 WHERE guild_id = $2",
            message, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Goodbye Message Updated",
            description=f"```{message}```",
            color=COLORS["accent"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ==================== PREFIX COMMANDS (TESTING) ====================
    
    @commands.command(name="wtest", hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def test_welcome(self, ctx: commands.Context):
        """Test welcome message (admin only)."""
        await self.on_member_join(ctx.author)
        await ctx.message.add_reaction("✅")
    
    @commands.command(name="gtest", hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def test_goodbye(self, ctx: commands.Context):
        """Test goodbye message (admin only)."""
        await self.on_member_remove(ctx.author)
        await ctx.message.add_reaction("✅")


async def setup(bot):
    """Required function to load the module."""
    await bot.add_cog(WelcomeCog(bot))
