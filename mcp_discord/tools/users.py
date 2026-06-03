"""
User management tools for Discord MCP.
"""

import discord
from datetime import timedelta


def register_user_tools(mcp, get_guild):
    """Register all user-related tools."""
    
    @mcp.tool()
    async def get_user_info(
        user_id: str,
        guild_id: str = None
    ) -> str:
        """Get information about a user/member.
        
        Args:
            user_id: ID of the user
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        
        result = f"""**{member.display_name}** ({member.name})
ID: {member.id}
Created: {member.created_at.strftime('%Y-%m-%d')}
Joined: {member.joined_at.strftime('%Y-%m-%d') if member.joined_at else 'Unknown'}
Roles: {', '.join(roles) if roles else 'None'}
Bot: {'Yes' if member.bot else 'No'}
Status: {member.status}"""
        
        return result

    @mcp.tool()
    async def timeout_user(
        user_id: str,
        minutes: int = 10,
        reason: str = None,
        guild_id: str = None
    ) -> str:
        """Timeout a user (prevent them from interacting).
        
        Args:
            user_id: ID of the user
            minutes: Duration in minutes (max 40320 = 28 days)
            reason: Optional reason for the timeout
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        duration = timedelta(minutes=min(minutes, 40320))
        await member.timeout(duration, reason=reason)
        
        return f"Timed out {member.display_name} for {minutes} minutes"

    @mcp.tool()
    async def remove_timeout(
        user_id: str,
        guild_id: str = None
    ) -> str:
        """Remove timeout from a user.
        
        Args:
            user_id: ID of the user
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        await member.timeout(None)
        return f"Removed timeout from {member.display_name}"

    @mcp.tool()
    async def kick_user(
        user_id: str,
        reason: str = None,
        guild_id: str = None
    ) -> str:
        """Kick a user from the server.
        
        Args:
            user_id: ID of the user to kick
            reason: Optional reason for the kick
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        name = member.display_name
        await member.kick(reason=reason)
        return f"Kicked {name}"

    @mcp.tool()
    async def ban_user(
        user_id: str,
        reason: str = None,
        delete_days: int = 0,
        guild_id: str = None
    ) -> str:
        """Ban a user from the server.
        
        Args:
            user_id: ID of the user to ban
            reason: Optional reason for the ban
            delete_days: Days of messages to delete (0-7)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        name = member.display_name
        await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
        return f"Banned {name}"

    @mcp.tool()
    async def unban_user(
        user_id: str,
        guild_id: str = None
    ) -> str:
        """Unban a user from the server.
        
        Args:
            user_id: ID of the user to unban
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        try:
            # Use discord.Object instead of fetching user - unban only needs the ID
            user = discord.Object(id=int(user_id))
            await guild.unban(user)
            return f"Unbanned user {user_id}"
        except discord.NotFound:
            return f"User {user_id} not found in ban list"

    @mcp.tool()
    async def get_banned_users(
        guild_id: str = None
    ) -> str:
        """Get a list of all banned users in the server.
        
        Args:
            guild_id: Optional guild ID
            
        Returns:
            JSON list of banned users with their IDs, names, and ban reasons.
        """
        import json
        
        guild = await get_guild(guild_id)
        
        bans = []
        async for ban_entry in guild.bans():
            bans.append({
                "id": str(ban_entry.user.id),
                "name": ban_entry.user.name,
                "display_name": ban_entry.user.display_name,
                "reason": ban_entry.reason or "No reason provided"
            })
        
        if not bans:
            return json.dumps({"count": 0, "bans": [], "message": "No banned users"})
        
        return json.dumps({
            "count": len(bans),
            "bans": bans,
            "message": f"Found {len(bans)} banned user(s)"
        })

    @mcp.tool()
    async def change_nickname(
        user_id: str,
        nickname: str,
        guild_id: str = None
    ) -> str:
        """Change a user's nickname.
        
        Args:
            user_id: ID of the user
            nickname: New nickname (empty string to remove)
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        
        if not member:
            return f"Member {user_id} not found"
        
        old_nick = member.display_name
        await member.edit(nick=nickname if nickname else None)
        return f"Changed nickname from {old_nick} to {nickname or member.name}"

    @mcp.tool()
    async def list_members(
        limit: int = 50,
        guild_id: str = None
    ) -> str:
        """List members in the server.
        
        Args:
            limit: Max members to list
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        result = f"Members in {guild.name} ({guild.member_count} total):\n\n"
        
        count = 0
        for member in guild.members:
            if count >= limit:
                result += f"\n... and {guild.member_count - count} more"
                break
            
            status_emoji = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡",
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }.get(member.status, "⚫")
            
            result += f"{status_emoji} {member.display_name} (ID: {member.id})\n"
            count += 1
        
        return result

    @mcp.tool()
    async def find_member(
        query: str,
        guild_id: str = None
    ) -> str:
        """Find members by name, nickname, partial match, or ID. Smart fuzzy search.
        
        Args:
            query: Name (full or partial), nickname, or user ID to search for
            guild_id: Optional guild ID
            
        Returns:
            JSON with matching members. Use the ID from results for other operations.
        """
        import json
        import re
        
        # Validate query is not empty
        if not query or not query.strip():
            return json.dumps({
                "found": False,
                "matches": [],
                "message": "Error: Query cannot be empty"
            })
        
        guild = await get_guild(guild_id)
        
        # Try ID first
        if query.isdigit():
            member = guild.get_member(int(query))
            if member:
                return json.dumps({
                    "found": True,
                    "match": {"id": str(member.id), "name": member.name, "display_name": member.display_name},
                    "message": f"Found member by ID: {member.display_name}"
                })
        
        # Normalize query
        query_clean = query.lower().strip()
        query_clean = re.sub(r'^[@#]', '', query_clean)
        
        matches = []
        
        for member in guild.members:
            name_lower = member.name.lower()
            display_lower = member.display_name.lower()
            nick_lower = member.nick.lower() if member.nick else ""
            
            # Clean names
            name_clean = re.sub(r'[^\w\s]', '', name_lower)
            display_clean = re.sub(r'[^\w\s]', '', display_lower)
            
            score = 0
            
            # Exact matches
            if query_clean in [name_lower, display_lower, nick_lower]:
                score = 100
            # Starts with
            elif any(n.startswith(query_clean) for n in [name_lower, display_lower, nick_lower] if n):
                score = 80
            # Contains
            elif any(query_clean in n for n in [name_lower, display_lower, nick_lower, name_clean, display_clean] if n):
                score = 60
            
            if score > 0:
                roles = [r.name for r in member.roles if r.name != "@everyone"]
                matches.append({
                    "id": str(member.id),
                    "name": member.name,
                    "display_name": member.display_name,
                    "roles": roles,
                    "bot": member.bot,
                    "score": score
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        if not matches:
            return json.dumps({
                "found": False,
                "matches": [],
                "message": f"No members found matching '{query}'"
            })
        
        best = matches[0]
        return json.dumps({
            "found": True,
            "match": {
                "id": best["id"], 
                "name": best["name"], 
                "display_name": best["display_name"],
                "roles": best["roles"]
            },
            "alternatives": [{"id": m["id"], "name": m["display_name"]} for m in matches[1:5]],
            "message": f"Best match: {best['display_name']} (ID: {best['id']}). Roles: {', '.join(best['roles']) if best['roles'] else 'None'}"
        })

