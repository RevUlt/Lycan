"""
Lycan Bot - Reaction Roles Module
Assigns roles based on reactions to specific messages.
"""

import discord
from discord.ext import commands
import logging

logger = logging.getLogger("LYCAN")


class ReactionRolesCog(commands.Cog):
    """Handles reaction-based role assignment."""
    
    def __init__(self, bot):
        self.bot = bot
        # Cache of reaction role configs: {message_id: {emoji: role_id}}
        self._cache = {}
    
    async def cog_load(self):
        """Load reaction role configs from database."""
        await self._ensure_table()
        await self._load_cache()
    
    async def _ensure_table(self):
        """Create table if not exists."""
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                emoji TEXT NOT NULL,
                role_id BIGINT NOT NULL,
                UNIQUE(message_id, emoji)
            )
        """)
    
    async def _load_cache(self):
        """Load all reaction role configs into memory."""
        rows = await self.bot.db.fetch("SELECT * FROM reaction_roles")
        for row in rows:
            msg_id = row['message_id']
            if msg_id not in self._cache:
                self._cache[msg_id] = {}
            self._cache[msg_id][row['emoji']] = row['role_id']
        logger.info(f"Loaded {len(rows)} reaction role configs")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction add - assign role."""
        if payload.user_id == self.bot.user.id:
            return  # Ignore bot's own reactions
        
        msg_id = payload.message_id
        emoji = str(payload.emoji)
        
        if msg_id not in self._cache:
            return
        
        if emoji not in self._cache[msg_id]:
            return
        
        role_id = self._cache[msg_id][emoji]
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        member = guild.get_member(payload.user_id)
        if not member:
            return
        
        role = guild.get_role(role_id)
        if not role:
            return
        
        try:
            await member.add_roles(role, reason="Reaction role")
            logger.info(f"Added role {role.name} to {member.name}")
        except discord.Forbidden:
            logger.warning(f"Cannot add role {role.name} - missing permissions")
        except Exception as e:
            logger.error(f"Error adding role: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction remove - remove role."""
        if payload.user_id == self.bot.user.id:
            return
        
        msg_id = payload.message_id
        emoji = str(payload.emoji)
        
        if msg_id not in self._cache:
            return
        
        if emoji not in self._cache[msg_id]:
            return
        
        role_id = self._cache[msg_id][emoji]
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        member = guild.get_member(payload.user_id)
        if not member:
            return
        
        role = guild.get_role(role_id)
        if not role:
            return
        
        try:
            await member.remove_roles(role, reason="Reaction role removed")
            logger.info(f"Removed role {role.name} from {member.name}")
        except discord.Forbidden:
            logger.warning(f"Cannot remove role {role.name} - missing permissions")
        except Exception as e:
            logger.error(f"Error removing role: {e}")
    
    async def add_reaction_role(self, message_id: int, channel_id: int, guild_id: int, emoji: str, role_id: int):
        """Add a reaction role config."""
        await self.bot.db.execute("""
            INSERT INTO reaction_roles (guild_id, channel_id, message_id, emoji, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (message_id, emoji) DO UPDATE SET role_id = $5
        """, guild_id, channel_id, message_id, emoji, role_id)
        
        # Update cache
        if message_id not in self._cache:
            self._cache[message_id] = {}
        self._cache[message_id][emoji] = role_id
    
    async def remove_reaction_role(self, message_id: int, emoji: str):
        """Remove a reaction role config."""
        await self.bot.db.execute(
            "DELETE FROM reaction_roles WHERE message_id = $1 AND emoji = $2",
            message_id, emoji
        )
        
        # Update cache
        if message_id in self._cache and emoji in self._cache[message_id]:
            del self._cache[message_id][emoji]


async def setup(bot):
    await bot.add_cog(ReactionRolesCog(bot))
