"""
Channel management tools for Discord MCP.
"""

import discord


def register_channel_tools(mcp, get_guild):
    """Register all channel-related tools."""
    
    @mcp.tool()
    async def create_text_channel(
        name: str,
        category_id: str = None,
        topic: str = None,
        guild_id: str = None
    ) -> str:
        """Create a new text channel in the server.
        
        Args:
            name: Name of the channel
            category_id: Optional category to place the channel in
            topic: Optional channel topic/description
            guild_id: Optional guild ID (uses default if not provided)
        """
        guild = await get_guild(guild_id)
        category = None
        
        if category_id:
            category = guild.get_channel(int(category_id))
        
        channel = await guild.create_text_channel(
            name=name,
            category=category,
            topic=topic
        )
        return f"Created text channel #{channel.name} (ID: {channel.id})"

    @mcp.tool()
    async def create_voice_channel(
        name: str,
        category_id: str = None,
        user_limit: int = 0,
        guild_id: str = None
    ) -> str:
        """Create a new voice channel in the server.
        
        Args:
            name: Name of the channel
            category_id: Optional category to place the channel in
            user_limit: Max users (0 = unlimited)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        category = None
        
        if category_id:
            category = guild.get_channel(int(category_id))
        
        channel = await guild.create_voice_channel(
            name=name,
            category=category,
            user_limit=user_limit
        )
        return f"Created voice channel {channel.name} (ID: {channel.id})"

    @mcp.tool()
    async def create_category(
        name: str,
        guild_id: str = None
    ) -> str:
        """Create a new category in the server.
        
        Args:
            name: Name of the category
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        category = await guild.create_category(name=name)
        return f"Created category {category.name} (ID: {category.id})"

    @mcp.tool()
    async def delete_channel(
        channel_id: str,
        guild_id: str = None
    ) -> str:
        """Delete a channel from the server.
        
        Args:
            channel_id: ID of the channel to delete
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        name = channel.name
        await channel.delete()
        return f"Deleted channel {name}"

    @mcp.tool()
    async def edit_channel(
        channel_id: str,
        name: str = None,
        topic: str = None,
        guild_id: str = None
    ) -> str:
        """Edit a channel's properties.
        
        Args:
            channel_id: ID of the channel to edit
            name: New name for the channel
            topic: New topic for the channel
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
        
        kwargs = {}
        if name:
            kwargs["name"] = name
        if topic is not None:
            kwargs["topic"] = topic
        
        await channel.edit(**kwargs)
        return f"Updated channel {channel.name}"

    @mcp.tool()
    async def set_channel_permissions(
        channel_id: str,
        target_id: str,
        target_type: str = "user",
        allow: str = None,
        deny: str = None,
        guild_id: str = None
    ) -> str:
        """Set permissions for a user or role in a channel.
        
        Args:
            channel_id: ID of the channel
            target_id: ID of the user or role
            target_type: "user" | "member" or "role"
            allow: Comma-separated list of permissions to allow
            deny: Comma-separated list of permissions to deny
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        channel = guild.get_channel(int(channel_id))
        
        if not channel:
            return f"Channel {channel_id} not found"
            
        # Determine target
        target = None
        if target_type.lower() in ["user", "member"]:
            target = guild.get_member(int(target_id))
            if not target:
                 return f"Member {target_id} not found"
        elif target_type.lower() == "role":
            target = guild.get_role(int(target_id))
            if not target:
                 return f"Role {target_id} not found"
        else:
            return "Invalid target_type. Use 'user' or 'role'"

        # Create permission overwrite
        import discord
        overwrite = discord.PermissionOverwrite()
        
        if allow:
            for perm in allow.split(","):
                perm = perm.strip().lower()
                if hasattr(overwrite, perm):
                    setattr(overwrite, perm, True)
                    
        if deny:
            for perm in deny.split(","):
                perm = perm.strip().lower()
                if hasattr(overwrite, perm):
                    setattr(overwrite, perm, False)
                    
        await channel.set_permissions(target, overwrite=overwrite)
        return f"Updated permissions for {target.name} in {channel.name}"

    @mcp.tool()
    async def list_channels(
        guild_id: str = None
    ) -> str:
        """List all channels in the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        result = f"Channels in {guild.name}:\n\n"
        
        for category in guild.categories:
            result += f"📁 {category.name} (ID: {category.id})\n"
            for channel in category.channels:
                prefix = "📝" if isinstance(channel, discord.TextChannel) else "🔊"
                result += f"  {prefix} {channel.name} (ID: {channel.id})\n"
        
        # Channels without category
        orphans = [c for c in guild.channels if c.category is None and not isinstance(c, discord.CategoryChannel)]
        if orphans:
            result += "\n(No category):\n"
            for channel in orphans:
                prefix = "📝" if isinstance(channel, discord.TextChannel) else "🔊"
                result += f"  {prefix} {channel.name} (ID: {channel.id})\n"
        
        return result

    @mcp.tool()
    async def find_category(
        query: str,
        guild_id: str = None
    ) -> str:
        """Find a category by name, partial match, or ID. Smart fuzzy search.
        
        Args:
            query: Name (full or partial), or category ID to search for
            guild_id: Optional guild ID
            
        Returns:
            JSON with matching categories. Use the ID for channel operations.
        """
        import json
        import re
        
        guild = await get_guild(guild_id)
        
        # Try ID first
        if query.isdigit():
            cat = guild.get_channel(int(query))
            if cat and isinstance(cat, discord.CategoryChannel):
                return json.dumps({
                    "found": True,
                    "match": {"id": str(cat.id), "name": cat.name, "channels": len(cat.channels)},
                    "message": f"Found category by ID: {cat.name}"
                })
        
        query_clean = query.lower().strip()
        matches = []
        
        for cat in guild.categories:
            name_lower = cat.name.lower()
            name_clean = re.sub(r'[^\w\s]', '', name_lower).replace('-', ' ').replace('_', ' ')
            name_clean = ' '.join(name_clean.split())
            
            score = 0
            
            if query_clean == name_lower or query_clean == name_clean:
                score = 100
            elif name_lower.startswith(query_clean) or name_clean.startswith(query_clean):
                score = 80
            elif query_clean in name_lower or query_clean in name_clean:
                score = 60
            
            if score > 0:
                matches.append({
                    "id": str(cat.id),
                    "name": cat.name,
                    "channels": len(cat.channels),
                    "score": score
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        if not matches:
            return json.dumps({
                "found": False,
                "matches": [],
                "message": f"No categories found matching '{query}'"
            })
        
        best = matches[0]
        return json.dumps({
            "found": True,
            "match": {"id": best["id"], "name": best["name"], "channels": best["channels"]},
            "alternatives": [{"id": m["id"], "name": m["name"]} for m in matches[1:5]],
            "message": f"Best match: {best['name']} (ID: {best['id']})"
        })

    @mcp.tool()
    async def find_channel(
        query: str,
        guild_id: str = None
    ) -> str:
        """Find a channel by name, partial match, or ID. Smart fuzzy search.
        
        Args:
            query: Name (full or partial), or channel ID to search for
            guild_id: Optional guild ID
            
        Returns:
            JSON with matching channels. Use the ID from results for other operations.
        """
        import json
        import re
        
        guild = await get_guild(guild_id)
        
        # Try ID first (exact match)
        if query.isdigit():
            channel = guild.get_channel(int(query))
            if channel:
                return json.dumps({
                    "found": True,
                    "match": {"id": str(channel.id), "name": channel.name, "type": str(channel.type)},
                    "message": f"Found channel by ID: {channel.name}"
                })
        
        # Normalize query for fuzzy matching
        query_clean = query.lower().strip()
        # Remove common prefixes/symbols
        query_clean = re.sub(r'^[#@]', '', query_clean)
        
        matches = []
        
        for channel in guild.channels:
            # Skip categories for most operations
            if isinstance(channel, discord.CategoryChannel):
                continue
                
            # Clean channel name for comparison
            name_lower = channel.name.lower()
            # Remove emoji (unicode) and special chars for matching
            name_clean = re.sub(r'[^\w\s]', '', name_lower).replace('-', ' ').replace('_', ' ')
            name_clean = ' '.join(name_clean.split())  # Normalize spaces
            
            score = 0
            
            # Exact match (highest priority)
            if query_clean == name_lower or query_clean == name_clean:
                score = 100
            # Starts with query
            elif name_lower.startswith(query_clean) or name_clean.startswith(query_clean):
                score = 80
            # Contains query
            elif query_clean in name_lower or query_clean in name_clean:
                score = 60
            # Query words appear in name
            elif all(word in name_clean for word in query_clean.split()):
                score = 40
            
            if score > 0:
                matches.append({
                    "id": str(channel.id),
                    "name": channel.name,
                    "type": str(channel.type),
                    "score": score
                })
        
        # Sort by score (best match first)
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        if not matches:
            return json.dumps({
                "found": False,
                "matches": [],
                "message": f"No channels found matching '{query}'"
            })
        
        # Return best match + alternatives
        best = matches[0]
        return json.dumps({
            "found": True,
            "match": {"id": best["id"], "name": best["name"], "type": best["type"]},
            "alternatives": [{"id": m["id"], "name": m["name"]} for m in matches[1:5]],
            "message": f"Best match: {best['name']} (ID: {best['id']})"
        })

