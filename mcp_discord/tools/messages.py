"""
Message management tools for Discord MCP.
"""

import discord


def register_message_tools(mcp, get_guild):
    """Register all message-related tools."""
    
    @mcp.tool()
    async def send_message(
        channel_id: str,
        content: str,
        guild_id: str = None
    ) -> str:
        """Send a plain text message to a channel. Use this ONLY for simple text without formatting.
        For formatted messages with titles, colors, or fields, use send_embed or send_embed_with_fields instead.
        
        Args:
            channel_id: ID of the channel to send to
            content: Plain text message content
            guild_id: Optional guild ID
        
        Example: send_message(channel_id="123", content="Hello everyone!")
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        # Security: Disable @everyone and @here mentions to prevent abuse
        allowed = discord.AllowedMentions(everyone=False, roles=False)
        message = await channel.send(content, allowed_mentions=allowed)
        return f"Message sent (ID: {message.id})"

    @mcp.tool()
    async def send_embed(
        channel_id: str,
        title: str,
        description: str = None,
        color: str = "3498db",
        footer: str = None,
        guild_id: str = None
    ) -> str:
        """Send a rich embed message to a channel. PREFERRED for announcements, rules, info, etc.
        Embeds have a colored bar, title, description, and optional footer.
        
        Args:
            channel_id: ID of the channel
            title: Embed title (required)
            description: Main text content of the embed
            color: Hex color without # (default: 3498db blue). Use ff0000 for red, 00ff00 for green, etc.
            footer: Small text at the bottom
            guild_id: Optional guild ID
        
        Example: send_embed(channel_id="123", title="Welcome!", description="Rules here...", color="5865F2")
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        # Validate Color
        try:
            color_int = 0
            if isinstance(color, str):
                c_str = color.strip().lower().lstrip('#')
                if c_str.startswith('0x'): c_str = c_str[2:]
                if not c_str: c_str = "3498db"
                try:
                    color_int = int(c_str, 16)
                except ValueError:
                    color_int = int(c_str)
            else:
                color_int = int(color)
        except:
             color_int = 0x3498db

        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int
        )
        
        if footer:
            embed.set_footer(text=footer)
        
        message = await channel.send(embed=embed)
        return f"Embed sent (ID: {message.id})"

    @mcp.tool()
    async def send_embed_with_fields(
        channel_id: str,
        title: str,
        fields: object,  # Changed from str to object to accept lists/dicts directly
        description: str = None,
        color: str = "3498db",
        guild_id: str = None
    ) -> str:
        """Send a rich embed with multiple field sections. BEST for rules, info lists, stats.
        
        Args:
            channel_id: ID of the channel
            title: Embed title (required)
            fields: List of fields. Supports multiple inputs:
                    1. JSON Structure (Preferred): [{"name":"Title", "value":"Content"}]
                    2. Pipe Format (Legacy): "Title:Content|Title2:Content2"
            description: Optional intro text before fields
            color: Hex color without # (default: 3498db)
            guild_id: Optional guild ID
        """
        import json as json_lib
        
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        # Validate Color
        try:
            color_int = 0
            if isinstance(color, str):
                c_str = color.strip().lower().lstrip('#')
                if c_str.startswith('0x'): c_str = c_str[2:]
                if not c_str: c_str = "3498db"
                try:
                    color_int = int(c_str, 16)
                except ValueError:
                    color_int = int(c_str)
            else:
                color_int = int(color)
        except:
             color_int = 0x3498db  # Fallback to default blue

        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int
        )
        
        # Parse fields logic - MAKE IT ROBUST
        parsed_fields = []
        
        # Case 1: It's already a list (from JSON parser)
        if isinstance(fields, list):
            for item in fields:
                if isinstance(item, dict):
                    name = item.get('name', item.get('title', 'Field'))
                    value = item.get('value', item.get('content', 'Empty'))
                    parsed_fields.append((name, value))
        
        # Case 2: It's a string (needs parsing)
        elif isinstance(fields, str):
            fields_stripped = fields.strip()
            
            # Subcase 2a: JSON String
            if fields_stripped.startswith('[') or fields_stripped.startswith('{'):
                try:
                    json_data = json_lib.loads(fields_stripped)
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict):
                                name = item.get('name', item.get('title', 'Field'))
                                value = item.get('value', item.get('content', 'Empty'))
                                parsed_fields.append((name, value))
                    elif isinstance(json_data, dict):
                         # Handle single object case
                         name = json_data.get('name', json_data.get('title', 'Field'))
                         value = json_data.get('value', json_data.get('content', 'Empty'))
                         parsed_fields.append((name, value))
                except:
                    pass # Fall through to pipe

            # Subcase 2b: Pipe Format (Fallback)
            if not parsed_fields:
                for field in fields.split("|"):
                    if ":" in field:
                        name, value = field.split(":", 1)
                        parsed_fields.append((name.strip(), value.strip()))
                    else:
                        # Handle case with no separator
                        parsed_fields.append(("Info", field.strip()))
        
        # Add fields to embed provided we have any
        if parsed_fields:
            for name, value in parsed_fields:
                embed.add_field(name=str(name), value=str(value), inline=False)
        else:
            return "Error: Could not parse 'fields'. Please use JSON format: [{'name':'...', 'value':'...'}]"
        
        message = await channel.send(embed=embed)
        return f"Embed with {len(parsed_fields)} fields sent (ID: {message.id})"

    @mcp.tool()
    async def delete_message(
        channel_id: str,
        message_id: str,
        guild_id: str = None
    ) -> str:
        """Delete a specific message.
        
        Args:
            channel_id: ID of the channel containing the message
            message_id: ID of the message to delete
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.delete()
            return f"Message {message_id} deleted"
        except discord.NotFound:
            return f"Message {message_id} not found"

    @mcp.tool()
    async def edit_message(
        channel_id: str,
        message_id: str,
        content: str,
        guild_id: str = None
    ) -> str:
        """Edit an existing message.
        
        Args:
            channel_id: ID of the channel containing the message
            message_id: ID of the message to edit
            content: New content for the message
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            # Security: Disable @everyone/@here in edited messages too
            allowed = discord.AllowedMentions(everyone=False, roles=False)
            await message.edit(content=content, allowed_mentions=allowed)
            return f"Message {message_id} edited"
        except discord.NotFound:
            return f"Message {message_id} not found"
        except discord.Forbidden:
            return f"Cannot edit message {message_id} (not bot's message or no permission)"

    @mcp.tool()
    async def edit_embed(
        channel_id: str,
        message_id: str,
        title: str = None,
        description: str = None,
        color: str = None,
        footer: str = None,
        guild_id: str = None
    ) -> str:
        """Edit an existing embed message.
        
        Args:
            channel_id: ID of the channel containing the message
            message_id: ID of the message to edit
            title: New embed title (optional, keeps old if not provided)
            description: New embed description (optional)
            color: New hex color without # (optional)
            footer: New footer text (optional)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            
            # Get existing embed or create new
            if message.embeds:
                old_embed = message.embeds[0]
                embed = discord.Embed(
                    title=title if title else old_embed.title,
                    description=description if description else old_embed.description,
                    color=int(color, 16) if color else old_embed.color
                )
                if footer:
                    embed.set_footer(text=footer)
                elif old_embed.footer:
                    embed.set_footer(text=old_embed.footer.text)
            else:
                embed = discord.Embed(
                    title=title or "Embed",
                    description=description or "",
                    color=int(color, 16) if color else 0x5865F2
                )
                if footer:
                    embed.set_footer(text=footer)
            
            await message.edit(embed=embed)
            return f"Embed {message_id} edited"
        except discord.NotFound:
            return f"Message {message_id} not found"
        except discord.Forbidden:
            return f"Cannot edit message {message_id} (not bot's message or no permission)"

    @mcp.tool()
    async def pin_message(
        channel_id: str,
        message_id: str,
        guild_id: str = None
    ) -> str:
        """Pin a message in a channel.
        
        Args:
            channel_id: ID of the channel
            message_id: ID of the message to pin
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.pin()
            return f"Message {message_id} pinned"
        except discord.NotFound:
            return f"Message {message_id} not found"

    @mcp.tool()
    async def react_to_message(
        channel_id: str,
        message_id: str,
        emoji: str,
        guild_id: str = None
    ) -> str:
        """Add a reaction to a message.
        
        Args:
            channel_id: ID of the channel
            message_id: ID of the message
            emoji: Emoji to react with (e.g., "👍" or custom emoji)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            return f"Reacted with {emoji}"
        except discord.NotFound:
            return f"Message {message_id} not found"

    @mcp.tool()
    async def unpin_message(
        channel_id: str,
        message_id: str,
        guild_id: str = None
    ) -> str:
        """Unpin a message in a channel.
        
        Args:
            channel_id: ID of the channel
            message_id: ID of the message to unpin
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.unpin()
            return f"Message {message_id} unpinned"
        except discord.NotFound:
            return f"Message {message_id} not found"

    @mcp.tool()
    async def get_pinned_messages(
        channel_id: str,
        guild_id: str = None
    ) -> str:
        """Get all pinned messages in a channel.
        
        Args:
            channel_id: ID of the channel
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
            
        pins = await channel.pins()
        if not pins:
            return "No pinned messages in this channel."
            
        result = f"Pinned messages in #{channel.name} ({len(pins)}):\n\n"
        for msg in pins:
            result += f"- [{msg.author.name}] {msg.content[:50]}... (ID: {msg.id})\n"
            
        return result

    @mcp.tool()
    async def remove_reaction(
        channel_id: str,
        message_id: str,
        emoji: str,
        guild_id: str = None,
        user_id: str = None
    ) -> str:
        """Remove a reaction from a message.
        
        Args:
            channel_id: ID of the channel
            message_id: ID of the message
            emoji: Emoji to remove (e.g., "👍")
            guild_id: Optional guild ID
            user_id: Optional user ID to remove reaction for (defaults to bot)
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        try:
            message = await channel.fetch_message(int(message_id))
            if user_id:
                member = guild.get_member(int(user_id))
                if not member:
                     return f"Member {user_id} not found"
                await message.remove_reaction(emoji, member)
                return f"Removed {emoji} from {member.display_name}"
            else:
                await message.remove_reaction(emoji, guild.me)
                return f"Removed {emoji} (bot reaction)"
        except discord.NotFound:
            return f"Message {message_id} not found"

    @mcp.tool()
    async def fetch_messages(
        channel_id: str,
        limit: int = 10,
        guild_id: str = None
    ) -> str:
        """Fetch recent messages from a channel.
        
        Args:
            channel_id: ID of the channel
            limit: Number of messages to fetch (max 100)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        limit = min(limit, 100)
        messages = []
        
        async for msg in channel.history(limit=limit):
            messages.append(f"[{msg.author.name}]: {msg.content[:100]}")
        
        result = f"Last {len(messages)} messages in #{channel.name}:\n\n"
        result += "\n".join(messages)
        
        return result
