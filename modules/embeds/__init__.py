"""
Lycan Bot - Embeds Module
Create, save and send custom embeds.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json


class EmbedModal(discord.ui.Modal, title="Create Embed"):
    """Modal for creating an embed."""
    
    embed_title = discord.ui.TextInput(
        label="Title",
        placeholder="My announcement embed",
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="The content of the embed...",
        max_length=4000
    )
    
    color = discord.ui.TextInput(
        label="Color (hex)",
        placeholder="#5865F2",
        max_length=7,
        required=False
    )
    
    image = discord.ui.TextInput(
        label="Image URL (optional)",
        placeholder="https://example.com/image.png",
        required=False
    )
    
    def __init__(self, bot, channel: discord.TextChannel = None, save_name: str = None):
        super().__init__()
        self.bot = bot
        self.channel = channel
        self.save_name = save_name
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse color
        try:
            color = discord.Color.from_str(self.color.value) if self.color.value else discord.Color.blurple()
        except ValueError:
            color = discord.Color.blurple()
        
        # Create embed
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.description.value,
            color=color
        )
        
        if self.image.value:
            embed.set_image(url=self.image.value)
        
        embed.set_footer(text=f"Created by {interaction.user.display_name}")
        
        # Save as template if name provided
        if self.save_name:
            embed_data = {
                "title": self.embed_title.value,
                "description": self.description.value,
                "color": str(color),
                "image": self.image.value
            }
            
            await self.bot.db.execute(
                """
                INSERT INTO embed_templates (guild_id, name, embed_data, created_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, name) DO UPDATE SET embed_data = EXCLUDED.embed_data
                """,
                interaction.guild_id, self.save_name, json.dumps(embed_data), interaction.user.id
            )
            
            await interaction.response.send_message(
                f"✅ Embed saved as **{self.save_name}**",
                embed=embed,
                ephemeral=True
            )
        elif self.channel:
            await self.channel.send(embed=embed)
            await interaction.response.send_message(
                f"✅ Embed sent to {self.channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EmbedsCog(commands.Cog):
    """Custom embed creator and manager."""
    
    def __init__(self, bot):
        self.bot = bot
    
    embed_group = app_commands.Group(
        name="embed",
        description="Create and manage custom embeds"
    )
    
    @embed_group.command(
        name="create",
        description="Create a new embed using a modal form"
    )
    @app_commands.describe(
        save_as="Optional name to save this embed as a template for later use"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_create(self, interaction: discord.Interaction, save_as: str = None):
        """Opens a modal to create an embed."""
        modal = EmbedModal(self.bot, save_name=save_as)
        await interaction.response.send_modal(modal)
    
    @embed_group.command(
        name="send",
        description="Send a saved embed to a channel"
    )
    @app_commands.describe(
        name="The name of the saved embed template",
        channel="The channel where the embed will be sent"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_send(self, interaction: discord.Interaction, name: str, channel: discord.TextChannel):
        """Send a saved embed to a channel."""
        row = await self.bot.db.fetchrow(
            "SELECT embed_data FROM embed_templates WHERE guild_id = $1 AND name = $2",
            interaction.guild_id, name
        )
        
        if not row:
            await interaction.response.send_message(
                f"❌ No embed found with name **{name}**",
                ephemeral=True
            )
            return
        
        data = json.loads(row['embed_data'])
        
        try:
            color = discord.Color.from_str(data.get('color', '#5865F2'))
        except:
            color = discord.Color.blurple()
        
        embed = discord.Embed(
            title=data.get('title'),
            description=data.get('description'),
            color=color
        )
        
        if data.get('image'):
            embed.set_image(url=data['image'])
        
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Embed **{name}** sent to {channel.mention}",
            ephemeral=True
        )
    
    @embed_group.command(
        name="list",
        description="List all saved embed templates"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_list(self, interaction: discord.Interaction):
        """List all saved embeds."""
        rows = await self.bot.db.fetch(
            "SELECT name, created_by, created_at FROM embed_templates WHERE guild_id = $1",
            interaction.guild_id
        )
        
        if not rows:
            await interaction.response.send_message("📭 No saved embeds.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Saved Embeds",
            color=discord.Color.blue()
        )
        
        for row in rows:
            embed.add_field(
                name=row['name'],
                value=f"Created: <t:{int(row['created_at'].timestamp())}:R>",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @embed_group.command(
        name="delete",
        description="Delete a saved embed template"
    )
    @app_commands.describe(
        name="The name of the embed template to delete"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_delete(self, interaction: discord.Interaction, name: str):
        """Delete a saved embed."""
        result = await self.bot.db.execute(
            "DELETE FROM embed_templates WHERE guild_id = $1 AND name = $2",
            interaction.guild_id, name
        )
        
        if result == "DELETE 0":
            await interaction.response.send_message(
                f"❌ No embed found with name **{name}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🗑️ Embed **{name}** deleted.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(EmbedsCog(bot))
