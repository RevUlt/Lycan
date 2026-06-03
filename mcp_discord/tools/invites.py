"""
Invite management tools for Discord MCP.
"""

import discord

def register_invite_tools(mcp, get_guild):
    """Register all invite-related tools."""

    @mcp.tool()
    async def create_invite(
        channel_id: str,
        max_age: int = 86400,
        max_uses: int = 0,
        temporary: bool = False,
        unique: bool = False,
        reason: str = None,
        guild_id: str = None
    ) -> str:
        """Create an invitation for a channel.
        
        Args:
            channel_id: ID of the channel
            max_age: Duration in seconds (0 for never expire, default 24h)
            max_uses: Max uses (0 for unlimited)
            temporary: Grant temporary membership
            unique: Ensure a unique invite URL
            reason: Reason for creating valid invite
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"

        invite = await channel.create_invite(
            max_age=max_age,
            max_uses=max_uses,
            temporary=temporary,
            unique=unique,
            reason=reason
        )
        
        return f"Invite created: {invite.url} (Code: {invite.code})"

    @mcp.tool()
    async def list_invites(
        guild_id: str = None
    ) -> str:
        """List all active invites in the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        invites = await guild.invites()
        
        if not invites:
            return "No active invites found."
            
        result = f"Active Invites ({len(invites)}):\n\n"
        for invite in invites:
            result += f"- Code: {invite.code}\n"
            result += f"  Channel: #{invite.channel.name if invite.channel else 'Unknown'}\n"
            result += f"  Inviter: {invite.inviter.name if invite.inviter else 'Unknown'}\n"
            result += f"  Uses: {invite.uses}/{invite.max_uses if invite.max_uses > 0 else '∞'}\n"
            result += f"  Expires: {invite.expires_at if invite.expires_at else 'Never'}\n\n"
            
        return result

    @mcp.tool()
    async def delete_invite(
        invite_code: str,
        reason: str = None,
        guild_id: str = None
    ) -> str:
        """Delete an invite.
        
        Args:
            invite_code: The invite code to delete
            reason: Reason for deletion
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        invites = await guild.invites()
        
        invite = discord.utils.get(invites, code=invite_code)
        
        if not invite:
            return f"Invite {invite_code} not found"
            
        await invite.delete(reason=reason)
        return f"Invite {invite_code} deleted"
