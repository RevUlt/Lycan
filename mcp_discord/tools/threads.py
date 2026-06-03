"""
Thread management tools for Discord MCP.
"""

import discord

def register_thread_tools(mcp, get_guild):
    """Register all thread-related tools."""

    @mcp.tool()
    async def create_thread(
        channel_id: str,
        name: str,
        message_id: str = None,
        auto_archive_duration: int = 1440,
        guild_id: str = None
    ) -> str:
        """Create a new thread in a text channel.
        
        Args:
            channel_id: ID of the channel to create thread in
            name: Name of the thread
            message_id: Optional ID of a message to start the thread on
            auto_archive_duration: Minutes before auto-archiving (60, 1440, 4320, 10080)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
            
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
             return f"Channel {channel.name} is not a text or forum channel"

        message = None
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                return f"Message {message_id} not found"

        thread = await channel.create_thread(
            name=name,
            message=message,
            auto_archive_duration=auto_archive_duration
        )
        
        return f"Created thread '{thread.name}' (ID: {thread.id})"

    @mcp.tool()
    async def archive_thread(
        thread_id: str,
        archived: bool = True,
        guild_id: str = None
    ) -> str:
        """Archive or unarchive a thread.
        
        Args:
            thread_id: ID of the thread
            archived: True to archive, False to unarchive
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        thread = guild.get_thread(int(thread_id)) or await guild.fetch_channel(int(thread_id))
        
        if not thread or not isinstance(thread, discord.Thread):
             return f"Thread {thread_id} not found"

        await thread.edit(archived=archived)
        return f"Thread '{thread.name}' {'archived' if archived else 'unarchived'}"

    @mcp.tool()
    async def lock_thread(
        thread_id: str,
        locked: bool = True,
        guild_id: str = None
    ) -> str:
        """Lock or unlock a thread.
        
        Args:
            thread_id: ID of the thread
            locked: True to lock, False to unlock
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        thread = guild.get_thread(int(thread_id)) or await guild.fetch_channel(int(thread_id))
        
        if not thread or not isinstance(thread, discord.Thread):
             return f"Thread {thread_id} not found"

        await thread.edit(locked=locked)
        return f"Thread '{thread.name}' {'locked' if locked else 'unlocked'}"
        
    @mcp.tool()
    async def list_threads(
        channel_id: str,
        guild_id: str = None
    ) -> str:
        """List active and archived threads in a channel.
        
        Args:
            channel_id: ID of the channel
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
            
        result = f"Threads in #{channel.name}:\n\n"
        
        # Active threads
        result += "Active Threads:\n"
        for thread in channel.threads:
            result += f"- {thread.name} (ID: {thread.id})\n"
            
        # Archived threads (fetch recent ones)
        result += "\nArchived Threads (Recent):\n"
        async for thread in channel.archived_threads(limit=10):
            result += f"- {thread.name} (ID: {thread.id})\n"
            
        return result
