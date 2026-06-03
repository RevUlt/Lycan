"""
Lycan Bot - Tickets Module
Professional support ticket system with elegant styling.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime


# Professional color palette
COLORS = {
    "normal": 0x3498DB,       # Professional blue
    "urgent": 0xE74C3C,       # Alert red
    "claimed": 0xF39C12,      # Orange (in progress)
    "closed": 0x95A5A6,       # Gray
    "accent": 0x2C3E50,       # Dark slate
}

LYCAN_ICON = ""
LYCAN_FOOTER = "Lycan Support"


class TicketCategorySelect(discord.ui.Select):
    """Dropdown to select ticket category."""
    
    def __init__(self, bot, categories: list):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=cat['name'],
                value=str(cat['id']),
                emoji=cat.get('emoji', '📋')
            )
            for cat in categories
        ]
        super().__init__(placeholder="Select a category...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        category_id = int(self.values[0])
        modal = TicketModal(self.bot, category_id)
        await interaction.response.send_modal(modal)


class TicketModal(discord.ui.Modal, title="Open Support Ticket"):
    """Modal for ticket description."""
    
    description = discord.ui.TextInput(
        label="Describe your issue",
        style=discord.TextStyle.paragraph,
        placeholder="Provide as much detail as possible...",
        max_length=1000
    )
    
    priority = discord.ui.TextInput(
        label="Priority (normal/urgent)",
        placeholder="normal",
        default="normal",
        max_length=10
    )
    
    def __init__(self, bot, category_id: int):
        super().__init__()
        self.bot = bot
        self.category_id = category_id
    
    async def on_submit(self, interaction: discord.Interaction):
        priority = "urgent" if "urgent" in self.priority.value.lower() else "normal"
        
        # Create private channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites
        )
        
        # Save to database
        await self.bot.db.execute(
            """
            INSERT INTO tickets (guild_id, channel_id, user_id, category_id, priority)
            VALUES ($1, $2, $3, $4, $5)
            """,
            interaction.guild_id, ticket_channel.id, interaction.user.id, 
            self.category_id, priority
        )
        
        # Professional ticket embed
        color = COLORS["urgent"] if priority == "urgent" else COLORS["normal"]
        priority_icon = "🔴" if priority == "urgent" else "🔵"
        
        embed = discord.Embed(
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=f"{LYCAN_ICON} New Support Ticket",
            icon_url=interaction.user.display_avatar.url
        )
        
        embed.add_field(
            name="📝 Issue Description",
            value=f"```{self.description.value}```",
            inline=False
        )
        
        embed.add_field(
            name="👤 Submitted By",
            value=f"{interaction.user.mention}\n`{interaction.user}`",
            inline=True
        )
        embed.add_field(
            name=f"{priority_icon} Priority",
            value=f"**{priority.upper()}**",
            inline=True
        )
        embed.add_field(
            name="📊 Status",
            value="⏳ Awaiting Response",
            inline=True
        )
        
        embed.set_footer(text=f"{LYCAN_FOOTER} • Ticket #{ticket_channel.id}")
        
        view = TicketControlView(self.bot, ticket_channel.id)
        await ticket_channel.send(embed=embed, view=view)
        
        # Greeting message
        greeting_embed = discord.Embed(
            description=f"Thank you for contacting support, {interaction.user.mention}.\n\nA team member will be with you shortly. Please provide any additional information that may help us assist you.",
            color=COLORS["accent"]
        )
        await ticket_channel.send(embed=greeting_embed)
        
        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True
        )


class TicketControlView(discord.ui.View):
    """Ticket management buttons for staff."""
    
    def __init__(self, bot, ticket_channel_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_channel_id = ticket_channel_id
    
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="✋")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Claim the ticket."""
        await self.bot.db.execute(
            "UPDATE tickets SET claimed_by = $1 WHERE channel_id = $2",
            interaction.user.id, self.ticket_channel_id
        )
        
        embed = discord.Embed(
            description=f"**{interaction.user.mention}** has claimed this ticket.",
            color=COLORS["claimed"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed)
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket."""
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Ticket Closed",
            description="This ticket has been resolved and will be archived.",
            color=COLORS["closed"],
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Closed By", value=interaction.user.mention)
        embed.set_footer(text=LYCAN_FOOTER)
        
        await interaction.response.send_message(embed=embed)
        
        # Update database
        await self.bot.db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = NOW() WHERE channel_id = $1",
            self.ticket_channel_id
        )
        
        # Delete after delay
        await interaction.followup.send("🗑️ Channel will be deleted in 10 seconds...")
        await discord.utils.sleep_until(datetime.utcnow().replace(second=datetime.utcnow().second + 10))
        await interaction.channel.delete(reason="Ticket closed")


class TicketPanelView(discord.ui.View):
    """Persistent panel view for opening tickets."""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.button(
        label="Open Ticket", 
        style=discord.ButtonStyle.primary, 
        emoji="🎫",
        custom_id="ticket_panel_open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open ticket selection menu."""
        categories = await self.bot.db.fetch(
            "SELECT * FROM ticket_categories WHERE guild_id = $1",
            interaction.guild_id
        )
        
        if not categories:
            # No categories - open modal directly
            modal = TicketModal(self.bot, None)
            await interaction.response.send_modal(modal)
        else:
            # Show category selection
            view = discord.ui.View()
            view.add_item(TicketCategorySelect(self.bot, [dict(c) for c in categories]))
            await interaction.response.send_message(
                "Please select a category:", 
                view=view, 
                ephemeral=True
            )


class TicketsCog(commands.Cog):
    """Professional ticket system with elegant embeds."""
    
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketPanelView(bot))
    
    tickets_group = app_commands.Group(
        name="tickets",
        description="Configure the support ticket system"
    )
    
    @tickets_group.command(
        name="setup",
        description="Send the ticket panel to a channel"
    )
    @app_commands.describe(
        channel="The channel where the ticket panel will be displayed"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tickets_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Setup the ticket panel."""
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Support Center",
            description="Need assistance? Click the button below to open a support ticket.\n\n**Please provide:**\n• A clear description of your issue\n• Any relevant screenshots or links\n• Steps to reproduce (if applicable)",
            color=COLORS["accent"]
        )
        embed.set_footer(text=f"{LYCAN_FOOTER} • {interaction.guild.name}")
        
        view = TicketPanelView(self.bot)
        await channel.send(embed=embed, view=view)
        
        response_embed = discord.Embed(
            title=f"{LYCAN_ICON} Ticket Panel Created",
            description=f"Panel sent to {channel.mention}",
            color=COLORS["normal"]
        )
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    @tickets_group.command(
        name="add_category",
        description="Add a ticket category"
    )
    @app_commands.describe(
        name="Category name",
        emoji="Emoji for this category"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_category(self, interaction: discord.Interaction, name: str, emoji: str = "📋"):
        """Add a ticket category."""
        await self.bot.db.execute(
            """
            INSERT INTO ticket_categories (guild_id, name, emoji)
            VALUES ($1, $2, $3)
            """,
            interaction.guild_id, name, emoji
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Category Added",
            description=f"{emoji} **{name}** is now available for tickets.",
            color=COLORS["normal"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @tickets_group.command(
        name="remove_category",
        description="Remove a ticket category"
    )
    @app_commands.describe(
        name="Name of the category to remove"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_category(self, interaction: discord.Interaction, name: str):
        """Remove a ticket category."""
        await self.bot.db.execute(
            "DELETE FROM ticket_categories WHERE guild_id = $1 AND name = $2",
            interaction.guild_id, name
        )
        
        embed = discord.Embed(
            title=f"{LYCAN_ICON} Category Removed",
            description=f"**{name}** has been removed.",
            color=COLORS["closed"]
        )
        embed.set_footer(text=LYCAN_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
