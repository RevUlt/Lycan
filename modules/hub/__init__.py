"""
Lycan Bot - Hub Module
Temporary voice channels created via /hub create command.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio


# Professional color palette
COLORS = {
    "primary": 0x3498DB,
    "success": 0x2ECC71,
    "warning": 0xF39C12,
    "error": 0xE74C3C,
    "accent": 0x2C3E50,
}

LYCAN_ICON = ""
LYCAN_FOOTER = "Lycan Hub"


class HubView(discord.ui.View):
    """Controls for the temporary voice room."""
    
    def __init__(self, bot, channel_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel_id = channel_id
        self.owner_id = owner_id
    
    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        """Verify the user is the room owner."""
        row = await self.bot.db.fetchrow(
            "SELECT owner_id FROM temp_channels WHERE channel_id = $1",
            self.channel_id
        )
        if not row or row['owner_id'] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the room owner can use these controls.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="hub:lock")
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return
        
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await self.bot.db.execute(
            "UPDATE temp_channels SET is_locked = TRUE WHERE channel_id = $1",
            self.channel_id
        )
        await interaction.response.send_message("🔒 Room locked.", ephemeral=True)
    
    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="hub:unlock")
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return
        
        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await self.bot.db.execute(
            "UPDATE temp_channels SET is_locked = FALSE WHERE channel_id = $1",
            self.channel_id
        )
        await interaction.response.send_message("🔓 Room unlocked.", ephemeral=True)
    
    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="hub:rename")
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        modal = RenameModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Limit", style=discord.ButtonStyle.primary, emoji="👥", custom_id="hub:limit")
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        modal = LimitModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.danger, emoji="👑", custom_id="hub:transfer", row=1)
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        modal = TransferModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Allow", style=discord.ButtonStyle.success, emoji="✅", custom_id="hub:allow", row=1)
    async def allow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        modal = AllowUserModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="hub:deny", row=1)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        
        modal = DenyUserModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)


class RenameModal(discord.ui.Modal, title="Rename Room"):
    """Modal to change the room name."""
    
    name = discord.ui.TextInput(
        label="New name",
        placeholder="My awesome room",
        max_length=100
    )
    
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            await channel.edit(name=self.name.value)
        await interaction.response.send_message(f"✅ Room renamed to **{self.name.value}**", ephemeral=True)


class LimitModal(discord.ui.Modal, title="User Limit"):
    """Modal to change the user limit."""
    
    limit = discord.ui.TextInput(
        label="Limit (0 = no limit)",
        placeholder="5",
        max_length=2
    )
    
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit.value)
            if limit < 0 or limit > 99:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ Enter a number between 0 and 99.", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            await channel.edit(user_limit=limit)
        await interaction.response.send_message(f"✅ Limit set to **{limit}** users", ephemeral=True)


class TransferModal(discord.ui.Modal, title="Transfer Ownership"):
    """Modal to transfer room ownership."""
    
    user_id = discord.ui.TextInput(
        label="New owner (User ID or @mention)",
        placeholder="123456789 or @username",
        max_length=50
    )
    
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse user ID from input
        user_input = self.user_id.value.strip()
        
        # Handle mention format <@123456789> or <@!123456789>
        if user_input.startswith("<@") and user_input.endswith(">"):
            user_input = user_input.replace("<@", "").replace("!", "").replace(">", "")
        
        try:
            new_owner_id = int(user_input)
            new_owner = interaction.guild.get_member(new_owner_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
            return
        
        if not new_owner:
            await interaction.response.send_message("❌ User not found in this server.", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return
        
        # Update database
        await self.bot.db.execute(
            "UPDATE temp_channels SET owner_id = $1 WHERE channel_id = $2",
            new_owner_id, self.channel_id
        )
        
        # Update permissions
        await channel.set_permissions(interaction.user, manage_channels=False)
        await channel.set_permissions(new_owner, manage_channels=True, connect=True, move_members=True)
        
        await interaction.response.send_message(
            f"👑 Ownership transferred to **{new_owner.display_name}**", 
            ephemeral=True
        )
        await channel.send(f"👑 **{new_owner.mention}** is now the owner of this room.")


class AllowUserModal(discord.ui.Modal, title="Allow User"):
    """Modal to allow a specific user into the room."""
    
    user_id = discord.ui.TextInput(
        label="User to allow (User ID or @mention)",
        placeholder="123456789 or @username",
        max_length=50
    )
    
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.user_id.value.strip()
        
        if user_input.startswith("<@") and user_input.endswith(">"):
            user_input = user_input.replace("<@", "").replace("!", "").replace(">", "")
        
        try:
            target_id = int(user_input)
            target = interaction.guild.get_member(target_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
            return
        
        if not target:
            await interaction.response.send_message("❌ User not found in this server.", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return
        
        await channel.set_permissions(target, connect=True, view_channel=True)
        await interaction.response.send_message(
            f"✅ **{target.display_name}** can now join this room.", 
            ephemeral=True
        )


class DenyUserModal(discord.ui.Modal, title="Deny User"):
    """Modal to deny a specific user from the room."""
    
    user_id = discord.ui.TextInput(
        label="User to deny (User ID or @mention)",
        placeholder="123456789 or @username",
        max_length=50
    )
    
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.user_id.value.strip()
        
        if user_input.startswith("<@") and user_input.endswith(">"):
            user_input = user_input.replace("<@", "").replace("!", "").replace(">", "")
        
        try:
            target_id = int(user_input)
            target = interaction.guild.get_member(target_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
            return
        
        if not target:
            await interaction.response.send_message("❌ User not found in this server.", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return
        
        # Deny access and kick if in channel
        await channel.set_permissions(target, connect=False, view_channel=False)
        
        if target.voice and target.voice.channel == channel:
            await target.move_to(None)  # Disconnect from voice
        
        await interaction.response.send_message(
            f"🚫 **{target.display_name}** has been denied access.", 
            ephemeral=True
        )


class HubCog(commands.Cog):
    """Temporary voice channels via /hub create."""
    
    def __init__(self, bot):
        self.bot = bot
        self.pending_rooms = {}  # user_id: channel_id (waiting for user to join)
    
    hub_group = app_commands.Group(
        name="hub",
        description="Create and manage temporary voice rooms"
    )
    
    @hub_group.command(
        name="setup",
        description="Set the category for temporary voice rooms"
    )
    @app_commands.describe(
        category="The category where rooms will be created"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def hub_setup(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Configure the hub category."""
        
        await self.bot.db.execute(
            """
            INSERT INTO guild_config (guild_id, hub_category_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET hub_category_id = EXCLUDED.hub_category_id
            """,
            interaction.guild_id, category.id
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Hub Configured",
            description=f"Temporary rooms will be created in **{category.name}**",
            color=COLORS["success"]
        )
        embed.add_field(
            name="Usage",
            value="Users can now use `/hub create` to create their own voice room.",
            inline=False
        )
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @hub_group.command(
        name="create",
        description="Create your own temporary voice room"
    )
    @app_commands.describe(
        name="Name for your room (optional)"
    )
    async def hub_create(self, interaction: discord.Interaction, name: str = None):
        """Create a temporary voice room."""
        
        # Check if hub is configured
        config = await self.bot.db.fetchrow(
            "SELECT hub_category_id FROM guild_config WHERE guild_id = $1",
            interaction.guild_id
        )
        
        if not config or not config['hub_category_id']:
            await interaction.response.send_message(
                "❌ Hub not configured. An admin needs to use `/hub setup` first.",
                ephemeral=True
            )
            return
        
        category = interaction.guild.get_channel(config['hub_category_id'])
        if not category:
            await interaction.response.send_message("❌ Hub category not found.", ephemeral=True)
            return
        
        # Room name
        room_name = name or f"{interaction.user.display_name}'s Room"
        
        # Create the voice channel
        channel = await interaction.guild.create_voice_channel(
            name=room_name,
            category=category
        )
        
        # Give owner permissions
        await channel.set_permissions(
            interaction.user,
            manage_channels=True,
            connect=True,
            move_members=True
        )
        
        # Save to database
        await self.bot.db.execute(
            "INSERT INTO temp_channels (channel_id, guild_id, owner_id) VALUES ($1, $2, $3)",
            channel.id, interaction.guild_id, interaction.user.id
        )
        
        # Check if user is already in a voice channel
        if interaction.user.voice and interaction.user.voice.channel:
            # Move user to the new room
            await interaction.user.move_to(channel)
            
            embed = discord.Embed(
                title=f"{LYCAN_ICON} Room Created",
                description=f"You've been moved to **{room_name}**",
                color=COLORS["success"]
            )
            embed.set_footer(text=LYCAN_FOOTER)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Send controls to the voice channel's text chat
            view = HubView(self.bot, channel.id, interaction.user.id)
            control_embed = discord.Embed(
                title=f"🎙️ {room_name}",
                description=f"{interaction.user.mention}, use these buttons to control your room.",
                color=COLORS["primary"]
            )
            control_embed.set_footer(text=LYCAN_FOOTER)
            await channel.send(embed=control_embed, view=view)
        
        else:
            # User not in voice - give them 2 minutes
            self.pending_rooms[interaction.user.id] = channel.id
            
            embed = discord.Embed(
                title=f"{LYCAN_ICON} Room Created",
                description=f"**{room_name}** is ready!\n\nYou have **2 minutes** to join, or the room will be deleted.",
                color=COLORS["warning"]
            )
            embed.add_field(
                name="📍 Your Room",
                value=channel.mention,
                inline=False
            )
            embed.set_footer(text=LYCAN_FOOTER)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Send controls to channel
            view = HubView(self.bot, channel.id, interaction.user.id)
            control_embed = discord.Embed(
                title=f"🎙️ {room_name}",
                description=f"Waiting for {interaction.user.mention} to join...",
                color=COLORS["primary"]
            )
            control_embed.set_footer(text=LYCAN_FOOTER)
            await channel.send(embed=control_embed, view=view)
            
            # Wait 2 minutes and check if user joined
            await asyncio.sleep(120)
            
            # Check if channel is empty and still pending
            if interaction.user.id in self.pending_rooms:
                del self.pending_rooms[interaction.user.id]
                
                # Verify channel still exists and is empty
                check_channel = interaction.guild.get_channel(channel.id)
                if check_channel and len(check_channel.members) == 0:
                    await check_channel.delete(reason="User didn't join in time")
                    await self.bot.db.execute(
                        "DELETE FROM temp_channels WHERE channel_id = $1",
                        channel.id
                    )
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice channel events - only for cleanup."""
        
        # User joined a channel - clear pending if they joined their room
        if after.channel and member.id in self.pending_rooms:
            if after.channel.id == self.pending_rooms[member.id]:
                del self.pending_rooms[member.id]
        
        # User left a channel - check if temp room is empty
        if before.channel:
            row = await self.bot.db.fetchrow(
                "SELECT channel_id FROM temp_channels WHERE channel_id = $1",
                before.channel.id
            )
            
            if row and len(before.channel.members) == 0:
                # Empty temp room - delete it
                await before.channel.delete(reason="Empty temporary room")
                await self.bot.db.execute(
                    "DELETE FROM temp_channels WHERE channel_id = $1",
                    before.channel.id
                )


async def setup(bot):
    await bot.add_cog(HubCog(bot))
