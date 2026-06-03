"""
Lycan Bot - Cleaning Module
Delete messages in bulk from channels.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class CleaningCog(commands.Cog):
    """Bulk message deletion utilities."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def _log_clean(self, guild_id: int, channel_id: int, moderator_id: int, 
                         count: int, filter_type: str) -> None:
        """Log the cleaning action to database."""
        await self.bot.db.execute(
            """
            INSERT INTO cleaning_logs (guild_id, channel_id, moderator_id, messages_deleted, filter_type)
            VALUES ($1, $2, $3, $4, $5)
            """,
            guild_id, channel_id, moderator_id, count, filter_type
        )
    
    clean_group = app_commands.Group(
        name="clean",
        description="Bulk delete messages from the current channel"
    )
    
    @clean_group.command(
        name="messages",
        description="Delete a specified number of messages"
    )
    @app_commands.describe(
        amount="Number of messages to delete (1-100)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clean_messages(self, interaction: discord.Interaction, amount: int):
        """Delete N messages from the channel."""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted = await interaction.channel.purge(limit=amount)
            
            try:
                await self._log_clean(
                    interaction.guild_id, interaction.channel_id, 
                    interaction.user.id, len(deleted), "messages"
                )
            except Exception as db_error:
                print(f"!!! DB Log error: {db_error}")
            
            await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)
        except Exception as e:
            print(f"!!! Clean command error: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @clean_group.command(
        name="user",
        description="Delete messages from a specific user"
    )
    @app_commands.describe(
        user="The user whose messages will be deleted",
        amount="Number of messages to check (1-100)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clean_user(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Delete N messages from a specific user."""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        def check(msg):
            return msg.author.id == user.id
        
        deleted = await interaction.channel.purge(limit=amount, check=check)
        
        await self._log_clean(
            interaction.guild_id, interaction.channel_id,
            interaction.user.id, len(deleted), f"user:{user.id}"
        )
        
        await interaction.followup.send(
            f"🗑️ Deleted **{len(deleted)}** messages from {user.mention}.", 
            ephemeral=True
        )
    
    @clean_group.command(
        name="bots",
        description="Delete messages sent by bots"
    )
    @app_commands.describe(
        amount="Number of messages to check (1-100)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clean_bots(self, interaction: discord.Interaction, amount: int):
        """Delete N messages from bots."""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        def check(msg):
            return msg.author.bot
        
        deleted = await interaction.channel.purge(limit=amount, check=check)
        
        await self._log_clean(
            interaction.guild_id, interaction.channel_id,
            interaction.user.id, len(deleted), "bots"
        )
        
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** bot messages.", ephemeral=True)
    
    @clean_group.command(
        name="contains",
        description="Delete messages containing specific text"
    )
    @app_commands.describe(
        text="The text to search for (case-insensitive)",
        amount="Number of messages to check (1-100)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clean_contains(self, interaction: discord.Interaction, text: str, amount: int):
        """Delete N messages containing the specified text."""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        def check(msg):
            return text.lower() in msg.content.lower()
        
        deleted = await interaction.channel.purge(limit=amount, check=check)
        
        await self._log_clean(
            interaction.guild_id, interaction.channel_id,
            interaction.user.id, len(deleted), f"contains:{text[:20]}"
        )
        
        await interaction.followup.send(
            f"🗑️ Deleted **{len(deleted)}** messages containing '{text}'.", 
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(CleaningCog(bot))
