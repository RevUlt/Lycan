"""
Voice management tools for Discord MCP.
"""

import discord

def register_voice_tools(mcp, get_guild):
    """Register all voice-related tools."""

    @mcp.tool()
    async def move_member(
        user_id: str,
        channel_id: str,
        guild_id: str = None
    ) -> str:
        """Move a member to a different voice channel.
        
        Args:
            user_id: ID of the user to move
            channel_id: ID of the destination voice channel
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        channel = guild.get_channel(int(channel_id))
        
        if not member:
            return f"Member {user_id} not found"
        if not channel:
             return f"Channel {channel_id} not found"
        if not isinstance(channel, discord.VoiceChannel):
             return f"Channel {channel.name} is not a voice channel"
        if not member.voice:
             return f"Member {member.display_name} is not in a voice channel"

        await member.move_to(channel)
        return f"Moved {member.display_name} to {channel.name}"

    @mcp.tool()
    async def disconnect_member(
        user_id: str,
        guild_id: str = None
    ) -> str:
        """Disconnect a member from voice.
        
        Args:
            user_id: ID of the user to disconnect
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        if not member.voice:
             return f"Member {member.display_name} is not in a voice channel"

        await member.move_to(None)
        return f"Disconnected {member.display_name} from voice"

    @mcp.tool()
    async def mute_member_voice(
        user_id: str,
        mute: bool = True,
        guild_id: str = None
    ) -> str:
        """Server mute/unmute a member in voice.
        
        Args:
            user_id: ID of the user
            mute: True to mute, False to unmute
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"

        await member.edit(mute=mute)
        return f"{'Muted' if mute else 'Unmuted'} {member.display_name} in voice"

    @mcp.tool()
    async def deafen_member_voice(
        user_id: str,
        deafen: bool = True,
        guild_id: str = None
    ) -> str:
        """Server deafen/undeafen a member in voice.
        
        Args:
            user_id: ID of the user
            deafen: True to deafen, False to undeafen
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"

        await member.edit(deafen=deafen)
        return f"{'Deafened' if deafen else 'Undeafened'} {member.display_name} in voice"
