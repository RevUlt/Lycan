"""
Role management tools for Discord MCP.
"""

import discord


def register_role_tools(mcp, get_guild):
    """Register all role-related tools."""
    
    @mcp.tool()
    async def create_role(
        name: str,
        color: str = "99aab5",
        permissions: str = None,
        mentionable: bool = False,
        guild_id: str = None
    ) -> str:
        """Create a new role.
        
        Args:
            name: Name of the role
            color: Hex color without # (default: gray)
            permissions: Comma-separated permissions (e.g., "send_messages,read_messages")
            mentionable: Whether the role can be mentioned
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        # Validate role name is not empty
        if not name or not name.strip():
            return "Error: Role name cannot be empty"
        
        # Validate/Parse Color
        try:
            color_int = 0
            if isinstance(color, str):
                # Clean string
                c_str = color.strip().lower().lstrip('#')
                if c_str.startswith('0x'):
                    c_str = c_str[2:]
                
                if not c_str: # Empty string -> default
                    c_str = "99aab5"

                # Try hex first (standard for Discord colors)
                try:
                    color_int = int(c_str, 16)
                except ValueError:
                    # Maybe it's a decimal string?
                    color_int = int(c_str)
            else:
                color_int = int(color)
            
            if not (0 <= color_int <= 16777215):
                 return f"Error: Color '{color}' is out of valid range (0-16777215 / 0x000000-0xFFFFFF)"
                 
        except ValueError:
            return f"Error: Invalid color format '{color}'. Use hex (e.g. 'FF0000') or integer."

        perms = discord.Permissions()
        if permissions:
            for perm in permissions.split(","):
                perm = perm.strip().lower()
                if hasattr(perms, perm):
                    setattr(perms, perm, True)
        
        try:
            role = await guild.create_role(
                name=name,
                color=discord.Color(color_int),
                permissions=perms,
                mentionable=mentionable
            )
        except Exception as e:
            return f"Discord API Error: {str(e)}"
        
        return f"Created role {role.name} (ID: {role.id})"

    @mcp.tool()
    async def delete_role(
        role_id: str,
        guild_id: str = None
    ) -> str:
        """Delete a role from the server.
        
        Args:
            role_id: ID of the role to delete
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        role = guild.get_role(int(role_id))
        
        if not role:
            return f"Role {role_id} not found"
        
        name = role.name
        await role.delete()
        return f"Deleted role {name}"

    @mcp.tool()
    async def edit_role(
        role_id: str,
        name: str = None,
        color: str = None,
        mentionable: bool = None,
        guild_id: str = None
    ) -> str:
        """Edit a role's properties.
        
        Args:
            role_id: ID of the role to edit
            name: New name for the role
            color: New hex color without #
            mentionable: Whether the role can be mentioned
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        role = guild.get_role(int(role_id))
        
        if not role:
            return f"Role {role_id} not found"
        
        kwargs = {}
        if name:
            kwargs["name"] = name
        if color:
            kwargs["color"] = discord.Color(int(color, 16))
        if mentionable is not None:
            kwargs["mentionable"] = mentionable
        
        await role.edit(**kwargs)
        return f"Updated role {role.name}"

    @mcp.tool()
    async def assign_role(
        user_id: str,
        role_id: str,
        guild_id: str = None
    ) -> str:
        """Assign a role to a user.
        
        Args:
            user_id: ID of the user
            role_id: ID of the role to assign
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        role = guild.get_role(int(role_id))
        
        if not member:
            return f"Member {user_id} not found"
        if not role:
            return f"Role {role_id} not found"
        
        await member.add_roles(role)
        return f"Assigned role {role.name} to {member.display_name}"

    @mcp.tool()
    async def remove_role(
        user_id: str,
        role_id: str,
        guild_id: str = None
    ) -> str:
        """Remove a role from a user.
        
        Args:
            user_id: ID of the user
            role_id: ID of the role to remove
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        member = guild.get_member(int(user_id))
        role = guild.get_role(int(role_id))
        
        if not member:
            return f"Member {user_id} not found"
        if not role:
            return f"Role {role_id} not found"
        
        await member.remove_roles(role)
        return f"Removed role {role.name} from {member.display_name}"

    @mcp.tool()
    async def list_roles(
        guild_id: str = None
    ) -> str:
        """List all roles in the server.
        
        Args:
            guild_id: Optional guild ID
        """
        guild = await get_guild(guild_id)
        
        result = f"Roles in {guild.name}:\n\n"
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if role.name == "@everyone":
                continue
            member_count = len(role.members)
            result += f"🎭 {role.name} (ID: {role.id}) - {member_count} members\n"
        
        return result

    @mcp.tool()
    async def find_role(
        query: str,
        guild_id: str = None
    ) -> str:
        """Find a role by name, partial match, or ID. Smart fuzzy search.
        
        Args:
            query: Name (full or partial), or role ID to search for
            guild_id: Optional guild ID
            
        Returns:
            JSON with matching roles. Use the ID from results for other operations.
        """
        import json
        import re
        
        guild = await get_guild(guild_id)
        
        # Try ID first
        if query.isdigit():
            role = guild.get_role(int(query))
            if role:
                return json.dumps({
                    "found": True,
                    "match": {"id": str(role.id), "name": role.name, "color": str(role.color), "members": len(role.members)},
                    "message": f"Found role by ID: {role.name}"
                })
        
        # Normalize query
        query_clean = query.lower().strip()
        query_clean = re.sub(r'^[@]', '', query_clean)
        
        matches = []
        
        for role in guild.roles:
            if role.name == "@everyone":
                continue
                
            name_lower = role.name.lower()
            name_clean = re.sub(r'[^\w\s]', '', name_lower).replace('-', ' ').replace('_', ' ')
            name_clean = ' '.join(name_clean.split())
            
            score = 0
            
            if query_clean == name_lower or query_clean == name_clean:
                score = 100
            elif name_lower.startswith(query_clean) or name_clean.startswith(query_clean):
                score = 80
            elif query_clean in name_lower or query_clean in name_clean:
                score = 60
            elif all(word in name_clean for word in query_clean.split()):
                score = 40
            
            if score > 0:
                matches.append({
                    "id": str(role.id),
                    "name": role.name,
                    "color": str(role.color),
                    "members": len(role.members),
                    "score": score
                })
        
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        if not matches:
            return json.dumps({
                "found": False,
                "matches": [],
                "message": f"No roles found matching '{query}'"
            })
        
        best = matches[0]
        return json.dumps({
            "found": True,
            "match": {"id": best["id"], "name": best["name"], "color": best["color"], "members": best["members"]},
            "alternatives": [{"id": m["id"], "name": m["name"]} for m in matches[1:5]],
            "message": f"Best match: {best['name']} (ID: {best['id']})"
        })

