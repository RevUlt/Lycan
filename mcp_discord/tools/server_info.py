"""
Server information tools for Discord MCP.
"""

import discord


def register_server_tools(mcp, get_guild):
    """Register all server information tools."""
    
    @mcp.tool()
    async def get_server_info(
        guild_id: str = None
    ) -> str:
        """Get detailed information about the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        categories = len(guild.categories)
        
        result = f"""**{guild.name}**
ID: {guild.id}
Owner: {guild.owner.display_name if guild.owner else 'Unknown'}
Created: {guild.created_at.strftime('%Y-%m-%d')}

**Members:** {guild.member_count}
**Roles:** {len(guild.roles)}
**Emojis:** {len(guild.emojis)}

**Channels:**
- Categories: {categories}
- Text: {text_channels}
- Voice: {voice_channels}

**Boosts:** Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)
**Verification:** {guild.verification_level}"""
        
        return result

    @mcp.tool()
    async def get_server_stats(
        guild_id: str = None
    ) -> str:
        """Get server statistics.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        online = len([m for m in guild.members if m.status != discord.Status.offline])
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        
        result = f"""**Server Stats: {guild.name}**

**Members:**
- Total: {guild.member_count}
- Online: {online}
- Humans: {humans}
- Bots: {bots}

**Activity:**
- Currently in voice: {sum(len(vc.members) for vc in guild.voice_channels)}"""
        
        return result

    @mcp.tool()
    async def list_emojis(
        guild_id: str = None
    ) -> str:
        """List all custom emojis in the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        if not guild.emojis:
            return "No custom emojis in this server"
        
        result = f"Custom emojis in {guild.name}:\n\n"
        
        for emoji in guild.emojis:
            animated = "🎬" if emoji.animated else ""
            result += f"{animated} :{emoji.name}: (ID: {emoji.id})\n"
        
        return result

    @mcp.tool()
    async def list_invites(
        guild_id: str = None
    ) -> str:
        """List all active invites for the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            return "No permission to view invites"
        
        if not invites:
            return "No active invites"
        
        result = f"Active invites for {guild.name}:\n\n"
        
        for invite in invites:
            uses = f"Uses: {invite.uses}" if invite.uses is not None else ""
            result += f"- {invite.code} by {invite.inviter.name if invite.inviter else 'Unknown'} → #{invite.channel.name} {uses}\n"
        
        return result

    @mcp.tool()
    async def create_invite(
        channel_id: str,
        max_age: int = 86400,
        max_uses: int = 0,
        guild_id: str = None
    ) -> str:
        """Create an invite link for a channel.
        
        Args:
            channel_id: ID of the channel
            max_age: Invite expiry in seconds (0 = never)
            max_uses: Max uses (0 = unlimited)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        invite = await channel.create_invite(
            max_age=max_age,
            max_uses=max_uses
        )
        
        return f"Created invite: https://discord.gg/{invite.code}"

    @mcp.tool()
    async def get_audit_log(
        limit: int = 10,
        guild_id: str = None
    ) -> str:
        """Get recent audit log entries.
        
        Args:
            limit: Number of entries to fetch
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        try:
            entries = []
            async for entry in guild.audit_logs(limit=min(limit, 50)):
                action = str(entry.action).replace("AuditLogAction.", "")
                user = entry.user.name if entry.user else "Unknown"
                target = str(entry.target) if entry.target else "N/A"
                entries.append(f"- {action} by {user} → {target}")
            
            if not entries:
                return "No audit log entries found"
            
            result = f"Recent audit log ({guild.name}):\n\n"
            result += "\n".join(entries)
            return result
            
        except discord.Forbidden:
            return "No permission to view audit logs"
