"""
Lycan Bot - Auditor Module
Server logging system with professional security-style embeds.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime


# Professional color palette for audit logs
COLORS = {
    "join": 0x2ECC71,         # Emerald green
    "leave": 0x95A5A6,        # Silver gray
    "ban": 0xC0392B,          # Dark red
    "edit": 0xF39C12,         # Orange
    "delete": 0xE74C3C,       # Red
    "voice": 0x3498DB,        # Blue
    "channel": 0x9B59B6,      # Purple
    "role": 0x1ABC9C,         # Teal
    "accent": 0x2C3E50,       # Dark slate
}

LYCAN_ICON = ""
LYCAN_FOOTER = "Lycan Security"


class AuditorCog(commands.Cog):
    """Server event logging system with professional styling."""
    
    def __init__(self, bot):
        self.bot = bot
    
    EVENTS = [
        "member_join", "member_leave", "member_ban", "member_kick",
        "message_edit", "message_delete", "bulk_delete",
        "channel_create", "channel_delete", 
        "role_create", "role_delete",
        "voice_join", "voice_leave"
    ]
    
    async def _get_config(self, guild_id: int) -> Optional[dict]:
        """Get auditor config from database."""
        row = await self.bot.db.fetchrow(
            "SELECT * FROM audit_config WHERE guild_id = $1",
            guild_id
        )
        return dict(row) if row else None
    
    async def _log_event(self, guild: discord.Guild, event_type: str, embed: discord.Embed) -> None:
        """Send log to the configured channel."""
        config = await self._get_config(guild.id)
        if not config or not config.get('log_channel_id'):
            return
        
        enabled = config.get('enabled_events', [])
        if event_type not in enabled:
            return
        
        channel = guild.get_channel(config['log_channel_id'])
        if channel:
            await channel.send(embed=embed)
    
    def _create_log_embed(self, title: str, color: int, **kwargs) -> discord.Embed:
        """Create a standardized audit log embed."""
        embed = discord.Embed(
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=title, icon_url=kwargs.get('icon_url'))
        
        if kwargs.get('description'):
            embed.description = kwargs['description']
        
        embed.set_footer(text=LYCAN_FOOTER)
        return embed
    
    audit_group = app_commands.Group(
        name="audit",
        description="Configure server event logging"
    )
    
    @audit_group.command(
        name="channel",
        description="Set the channel for audit logs"
    )
    @app_commands.describe(
        channel="The text channel where log messages will be sent"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def audit_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Configure the logging channel."""
        await self.bot.db.execute(
            """
            INSERT INTO audit_config (guild_id, log_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = EXCLUDED.log_channel_id
            """,
            interaction.guild_id, channel.id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Audit Channel Configured",
            description=f"Audit logs will be sent to {channel.mention}",
            color=COLORS["accent"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @audit_group.command(
        name="enable",
        description="Enable logging for a specific event type"
    )
    @app_commands.describe(
        event="The type of event to start logging"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(event=[
        app_commands.Choice(name=e.replace("_", " ").title(), value=e) for e in EVENTS
    ])
    async def audit_enable(self, interaction: discord.Interaction, event: str):
        """Enable an event for logging."""
        await self.bot.db.execute(
            """
            UPDATE audit_config 
            SET enabled_events = array_append(
                array_remove(enabled_events, $1), $1
            )
            WHERE guild_id = $2
            """,
            event, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Event Enabled",
            description=f"Now logging **{event.replace('_', ' ').title()}** events.",
            color=COLORS["join"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @audit_group.command(
        name="disable",
        description="Disable logging for a specific event type"
    )
    @app_commands.describe(
        event="The type of event to stop logging"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(event=[
        app_commands.Choice(name=e.replace("_", " ").title(), value=e) for e in EVENTS
    ])
    async def audit_disable(self, interaction: discord.Interaction, event: str):
        """Disable an event from logging."""
        await self.bot.db.execute(
            """
            UPDATE audit_config 
            SET enabled_events = array_remove(enabled_events, $1)
            WHERE guild_id = $2
            """,
            event, interaction.guild_id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Event Disabled",
            description=f"Stopped logging **{event.replace('_', ' ').title()}** events.",
            color=COLORS["leave"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @audit_group.command(
        name="list",
        description="View current audit log configuration"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def audit_list(self, interaction: discord.Interaction):
        """Show current configuration."""
        config = await self._get_config(interaction.guild_id)
        
        if not config:
            embed = discord.Embed(
                title=f"{LYCAN_ICON} Auditor Not Configured",
                description="Use `/audit channel` to set up logging.",
                color=COLORS["accent"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(config['log_channel_id']) if config.get('log_channel_id') else None
        enabled = config.get('enabled_events', [])
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Audit Configuration",
            color=COLORS["accent"],
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📍 Log Channel",
            value=channel.mention if channel else "*Not set*",
            inline=False
        )
        
        if enabled:
            events_formatted = ", ".join([f"`{e}`" for e in enabled])
            embed.add_field(
                name=f"✅ Active Events ({len(enabled)})",
                value=events_formatted,
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ Active Events",
                value="*No events enabled*",
                inline=False
            )
        
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ==================== EVENTS ====================
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = self._create_log_embed(
            "👤 Member Joined",
            COLORS["join"],
            icon_url=member.display_avatar.url
        )
        
        embed.description = f"{member.mention}\n`{member}` • ID: `{member.id}`"
        
        account_age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
        embed.add_field(
            name="Account Age",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True
        )
        
        if account_age < 7:
            embed.add_field(
                name="⚠️ New Account",
                value=f"Only {account_age} days old",
                inline=True
            )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._log_event(member.guild, "member_join", embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = self._create_log_embed(
            "👤 Member Left",
            COLORS["leave"]
        )
        
        embed.description = f"`{member}` • ID: `{member.id}`"
        
        if member.joined_at:
            days = (datetime.utcnow() - member.joined_at.replace(tzinfo=None)).days
            embed.add_field(
                name="Time in Server",
                value=f"**{days}** days",
                inline=True
            )
        
        await self._log_event(member.guild, "member_leave", embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = self._create_log_embed(
            "🔨 User Banned",
            COLORS["ban"]
        )
        
        embed.description = f"**{user}**\nID: `{user.id}`"
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await self._log_event(guild, "member_ban", embed)
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return
        
        embed = self._create_log_embed(
            "✏️ Message Edited",
            COLORS["edit"],
            icon_url=before.author.display_avatar.url
        )
        
        embed.description = f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}"
        
        before_content = before.content[:500] + "..." if len(before.content) > 500 else before.content
        after_content = after.content[:500] + "..." if len(after.content) > 500 else after.content
        
        embed.add_field(
            name="Before",
            value=f"```{before_content or 'Empty'}```",
            inline=False
        )
        embed.add_field(
            name="After",
            value=f"```{after_content or 'Empty'}```",
            inline=False
        )
        embed.add_field(
            name="Jump",
            value=f"[Go to message]({after.jump_url})",
            inline=True
        )
        
        await self._log_event(before.guild, "message_edit", embed)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        embed = self._create_log_embed(
            "🗑️ Message Deleted",
            COLORS["delete"],
            icon_url=message.author.display_avatar.url
        )
        
        embed.description = f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}"
        
        content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
        embed.add_field(
            name="Content",
            value=f"```{content or 'No text content'}```",
            inline=False
        )
        
        if message.attachments:
            embed.add_field(
                name="📎 Attachments",
                value="\n".join([a.filename for a in message.attachments[:5]]),
                inline=True
            )
        
        await self._log_event(message.guild, "message_delete", embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        
        if after.channel and not before.channel:
            embed = self._create_log_embed(
                "🔊 Voice Connected",
                COLORS["voice"]
            )
            embed.description = f"{member.mention} joined **{after.channel.name}**"
            await self._log_event(member.guild, "voice_join", embed)
        
        elif before.channel and not after.channel:
            embed = self._create_log_embed(
                "🔇 Voice Disconnected",
                COLORS["voice"]
            )
            embed.description = f"{member.mention} left **{before.channel.name}**"
            await self._log_event(member.guild, "voice_leave", embed)
        
        elif before.channel and after.channel:
            embed = self._create_log_embed(
                "🔀 Voice Moved",
                COLORS["voice"]
            )
            embed.description = f"{member.mention}\n**{before.channel.name}** → **{after.channel.name}**"
            await self._log_event(member.guild, "voice_join", embed)
    
    # ==================== ROLE EVENTS ====================
    
    # Bot IDs to exclude from logging
    EXCLUDED_BOTS = [
        1453336045889261632,  # Lycan
        1202840694893281290,  # Vasko
    ]
    
    async def _get_audit_executor(self, guild: discord.Guild, action: discord.AuditLogAction):
        """Get who performed the action from audit logs."""
        try:
            async for entry in guild.audit_logs(limit=1, action=action):
                return entry.user
        except:
            return None
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        executor = await self._get_audit_executor(role.guild, discord.AuditLogAction.role_create)
        
        # Skip if created by excluded bots
        if executor and executor.id in self.EXCLUDED_BOTS:
            return
        
        embed = self._create_log_embed(
            "🎭 Role Created",
            COLORS["role"]
        )
        embed.description = f"**{role.name}**\nID: `{role.id}`"
        
        if executor:
            embed.add_field(name="Created By", value=executor.mention, inline=True)
        
        embed.add_field(name="Color", value=str(role.color), inline=True)
        await self._log_event(role.guild, "role_create", embed)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        executor = await self._get_audit_executor(role.guild, discord.AuditLogAction.role_delete)
        
        if executor and executor.id in self.EXCLUDED_BOTS:
            return
        
        embed = self._create_log_embed(
            "🎭 Role Deleted",
            COLORS["delete"]
        )
        embed.description = f"**{role.name}**\nID: `{role.id}`"
        
        if executor:
            embed.add_field(name="Deleted By", value=executor.mention, inline=True)
        
        await self._log_event(role.guild, "role_delete", embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log role changes on members."""
        if before.roles == after.roles:
            return
        
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        
        if added:
            embed = self._create_log_embed(
                "👤 Role Added",
                COLORS["role"]
            )
            embed.description = f"{after.mention} received **{', '.join([r.name for r in added])}**"
            await self._log_event(after.guild, "role_create", embed)
        
        if removed:
            embed = self._create_log_embed(
                "👤 Role Removed",
                COLORS["leave"]
            )
            embed.description = f"{after.mention} lost **{', '.join([r.name for r in removed])}**"
            await self._log_event(after.guild, "role_delete", embed)
    
    # ==================== CHANNEL EVENTS ====================
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        executor = await self._get_audit_executor(channel.guild, discord.AuditLogAction.channel_create)
        
        if executor and executor.id in self.EXCLUDED_BOTS:
            return
        
        channel_type = "📝 Text" if isinstance(channel, discord.TextChannel) else \
                       "🔊 Voice" if isinstance(channel, discord.VoiceChannel) else \
                       "📁 Category" if isinstance(channel, discord.CategoryChannel) else "📌"
        
        embed = self._create_log_embed(
            f"{channel_type} Channel Created",
            COLORS["channel"]
        )
        embed.description = f"**{channel.name}**\nID: `{channel.id}`"
        
        if executor:
            embed.add_field(name="Created By", value=executor.mention, inline=True)
        
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        
        await self._log_event(channel.guild, "channel_create", embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        executor = await self._get_audit_executor(channel.guild, discord.AuditLogAction.channel_delete)
        
        if executor and executor.id in self.EXCLUDED_BOTS:
            return
        
        channel_type = "📝 Text" if isinstance(channel, discord.TextChannel) else \
                       "🔊 Voice" if isinstance(channel, discord.VoiceChannel) else \
                       "📁 Category" if isinstance(channel, discord.CategoryChannel) else "📌"
        
        embed = self._create_log_embed(
            f"{channel_type} Channel Deleted",
            COLORS["delete"]
        )
        embed.description = f"**{channel.name}**\nID: `{channel.id}`"
        
        if executor:
            embed.add_field(name="Deleted By", value=executor.mention, inline=True)
        
        await self._log_event(channel.guild, "channel_delete", embed)


async def setup(bot):
    await bot.add_cog(AuditorCog(bot))

