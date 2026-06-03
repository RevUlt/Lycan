"""
Lycan Bot - API Server
FastAPI integrado con el bot para control y testing.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import asyncio
import discord
from datetime import datetime


# ==================== MODELOS ====================

class WelcomeConfig(BaseModel):
    channel_id: int
    message: Optional[str] = None

class CleanRequest(BaseModel):
    channel_id: int
    count: int
    filter_type: str = "messages"  # messages, bots, user:<id>

class ChannelConfig(BaseModel):
    channel_id: int

class EmbedCreate(BaseModel):
    name: str
    title: str
    description: str
    color: Optional[str] = "#5865F2"
    image_url: Optional[str] = None

class EmbedSend(BaseModel):
    name: str
    channel_id: int

class HubConfig(BaseModel):
    category_id: int

class TicketCategoryCreate(BaseModel):
    name: str
    emoji: str = "📋"

class TicketCreate(BaseModel):
    user_id: int
    category_id: Optional[int] = None
    description: str
    priority: str = "normal"

class AuditConfig(BaseModel):
    channel_id: int
    enabled_events: list[str] = []

class SocialFeed(BaseModel):
    platform: str  # twitch or youtube
    username: str  # twitch username or youtube channel id
    channel_id: int  # discord channel id
    message: Optional[str] = None

class SocialTest(BaseModel):
    platform: str
    username: str
    channel_id: int


# ==================== API SERVER ====================

class LycanAPI:
    """Servidor FastAPI para control del bot."""
    
    def __init__(self, bot):
        self.bot = bot
        self.app = FastAPI(
            title="Lycan Bot API",
            description="API de control para el bot Lycan",
            version="1.0.0"
        )
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    async def _verify_api_key(self, x_api_key: str = Header(None)):
        """Verifica API key."""
        if x_api_key != self.bot.config.api_secret_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return True
    
    def _setup_routes(self):
        """Configura todas las rutas."""
        
        # ==================== GENERAL ====================
        
        @self.app.get("/")
        async def root():
            return {
                "name": "Lycan Bot API",
                "status": "online",
                "guilds": len(self.bot.guilds),
                "user": str(self.bot.user)
            }
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "db": self.bot.db is not None}
        
        @self.app.get("/guilds")
        async def list_guilds(auth: bool = Depends(self._verify_api_key)):
            return [
                {"id": g.id, "name": g.name, "members": g.member_count}
                for g in self.bot.guilds
            ]
        
        @self.app.get("/guilds/{guild_id}")
        async def get_guild(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            return {
                "id": guild.id,
                "name": guild.name,
                "members": guild.member_count,
                "channels": [{"id": c.id, "name": c.name, "type": str(c.type)} for c in guild.channels[:20]]
            }
        
        # ==================== WELCOME ====================
        
        @self.app.get("/guilds/{guild_id}/welcome")
        async def get_welcome(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            row = await self.bot.db.fetchrow(
                "SELECT welcome_channel_id, welcome_message, goodbye_channel_id, goodbye_message FROM guild_config WHERE guild_id = $1",
                guild_id
            )
            if not row:
                return {"configured": False}
            return dict(row)
        
        @self.app.post("/guilds/{guild_id}/welcome/channel")
        async def set_welcome_channel(guild_id: int, config: WelcomeConfig, auth: bool = Depends(self._verify_api_key)):
            await self.bot.db.execute(
                """
                INSERT INTO guild_config (guild_id, welcome_channel_id, welcome_message)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO UPDATE SET 
                    welcome_channel_id = EXCLUDED.welcome_channel_id,
                    welcome_message = COALESCE(EXCLUDED.welcome_message, guild_config.welcome_message)
                """,
                guild_id, config.channel_id, config.message
            )
            return {"success": True, "channel_id": config.channel_id}
        
        @self.app.post("/guilds/{guild_id}/welcome/test")
        async def test_welcome(guild_id: int, user_id: int, auth: bool = Depends(self._verify_api_key)):
            """Simula bienvenida para un usuario."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            member = guild.get_member(user_id)
            if not member:
                raise HTTPException(404, "Member not found")
            
            cog = self.bot.get_cog("WelcomeCog")
            if cog:
                await cog.on_member_join(member)
                return {"success": True, "message": f"Welcome triggered for {member}"}
            
            raise HTTPException(500, "WelcomeCog not loaded")
        
        @self.app.post("/guilds/{guild_id}/goodbye/channel")
        async def set_goodbye_channel(guild_id: int, channel: ChannelConfig, auth: bool = Depends(self._verify_api_key)):
            """Configura el canal de despedida."""
            await self.bot.db.execute(
                """
                INSERT INTO guild_config (guild_id, goodbye_channel_id)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO UPDATE SET goodbye_channel_id = EXCLUDED.goodbye_channel_id
                """,
                guild_id, channel.channel_id
            )
            return {"success": True, "channel_id": channel.channel_id}
        
        @self.app.post("/guilds/{guild_id}/goodbye/test")
        async def test_goodbye(guild_id: int, user_id: int, auth: bool = Depends(self._verify_api_key)):
            """Simula despedida para un usuario."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            member = guild.get_member(user_id)
            if not member:
                raise HTTPException(404, "Member not found")
            
            cog = self.bot.get_cog("WelcomeCog")
            if cog:
                await cog.on_member_remove(member)
                return {"success": True, "message": f"Goodbye triggered for {member}"}
            
            raise HTTPException(500, "WelcomeCog not loaded")
        
        # ==================== CLEANING ====================
        
        @self.app.post("/guilds/{guild_id}/clean")
        async def clean_messages(guild_id: int, req: CleanRequest, auth: bool = Depends(self._verify_api_key)):
            """Limpia mensajes en un canal."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            channel = guild.get_channel(req.channel_id)
            if not channel:
                raise HTTPException(404, "Channel not found")
            
            if req.count < 1 or req.count > 100:
                raise HTTPException(400, "Count must be between 1 and 100")
            
            if req.filter_type == "messages":
                deleted = await channel.purge(limit=req.count)
            elif req.filter_type == "bots":
                deleted = await channel.purge(limit=req.count, check=lambda m: m.author.bot)
            elif req.filter_type.startswith("user:"):
                user_id = int(req.filter_type.split(":")[1])
                deleted = await channel.purge(limit=req.count, check=lambda m: m.author.id == user_id)
            else:
                raise HTTPException(400, "Invalid filter_type")
            
            return {"success": True, "deleted": len(deleted)}
        
        @self.app.get("/guilds/{guild_id}/cleaning/logs")
        async def get_cleaning_logs(guild_id: int, limit: int = 20, auth: bool = Depends(self._verify_api_key)):
            rows = await self.bot.db.fetch(
                "SELECT * FROM cleaning_logs WHERE guild_id = $1 ORDER BY created_at DESC LIMIT $2",
                guild_id, limit
            )
            return [dict(r) for r in rows]
        
        # ==================== EMBEDS ====================
        
        @self.app.get("/guilds/{guild_id}/embeds")
        async def list_embeds(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            rows = await self.bot.db.fetch(
                "SELECT name, created_by, created_at FROM embed_templates WHERE guild_id = $1",
                guild_id
            )
            return [dict(r) for r in rows]
        
        @self.app.post("/guilds/{guild_id}/embeds")
        async def create_embed(guild_id: int, embed: EmbedCreate, auth: bool = Depends(self._verify_api_key)):
            import json
            embed_data = {
                "title": embed.title,
                "description": embed.description,
                "color": embed.color,
                "image": embed.image_url
            }
            await self.bot.db.execute(
                """
                INSERT INTO embed_templates (guild_id, name, embed_data, created_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, name) DO UPDATE SET embed_data = EXCLUDED.embed_data
                """,
                guild_id, embed.name, json.dumps(embed_data), 0
            )
            return {"success": True, "name": embed.name}
        
        @self.app.post("/guilds/{guild_id}/embeds/send")
        async def send_embed(guild_id: int, req: EmbedSend, auth: bool = Depends(self._verify_api_key)):
            import json
            import discord
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            channel = guild.get_channel(req.channel_id)
            if not channel:
                raise HTTPException(404, "Channel not found")
            
            row = await self.bot.db.fetchrow(
                "SELECT embed_data FROM embed_templates WHERE guild_id = $1 AND name = $2",
                guild_id, req.name
            )
            if not row:
                raise HTTPException(404, "Embed not found")
            
            data = json.loads(row['embed_data'])
            embed = discord.Embed(
                title=data.get('title'),
                description=data.get('description'),
                color=discord.Color.from_str(data.get('color', '#5865F2'))
            )
            if data.get('image'):
                embed.set_image(url=data['image'])
            
            await channel.send(embed=embed)
            return {"success": True, "channel": channel.name}
        
        # ==================== HUB ====================
        
        @self.app.get("/guilds/{guild_id}/hub")
        async def get_hub(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            row = await self.bot.db.fetchrow(
                "SELECT hub_category_id, hub_channel_id FROM guild_config WHERE guild_id = $1",
                guild_id
            )
            if not row or not row['hub_category_id']:
                return {"configured": False}
            return dict(row)
        
        @self.app.get("/guilds/{guild_id}/hub/channels")
        async def list_temp_channels(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            rows = await self.bot.db.fetch(
                "SELECT * FROM temp_channels WHERE guild_id = $1",
                guild_id
            )
            return [dict(r) for r in rows]
        
        # ==================== AUDITOR ====================
        
        @self.app.get("/guilds/{guild_id}/audit")
        async def get_audit_config(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            row = await self.bot.db.fetchrow(
                "SELECT * FROM audit_config WHERE guild_id = $1",
                guild_id
            )
            if not row:
                return {"configured": False}
            return dict(row)
        
        @self.app.post("/guilds/{guild_id}/audit")
        async def set_audit_config(guild_id: int, config: AuditConfig, auth: bool = Depends(self._verify_api_key)):
            await self.bot.db.execute(
                """
                INSERT INTO audit_config (guild_id, log_channel_id, enabled_events)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO UPDATE SET 
                    log_channel_id = EXCLUDED.log_channel_id,
                    enabled_events = EXCLUDED.enabled_events
                """,
                guild_id, config.channel_id, config.enabled_events
            )
            return {"success": True}
        
        # ==================== TICKETS ====================
        
        @self.app.get("/guilds/{guild_id}/tickets")
        async def list_tickets(guild_id: int, status: str = "open", auth: bool = Depends(self._verify_api_key)):
            rows = await self.bot.db.fetch(
                "SELECT * FROM tickets WHERE guild_id = $1 AND status = $2",
                guild_id, status
            )
            return [dict(r) for r in rows]
        
        @self.app.get("/guilds/{guild_id}/tickets/categories")
        async def list_ticket_categories(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            rows = await self.bot.db.fetch(
                "SELECT * FROM ticket_categories WHERE guild_id = $1",
                guild_id
            )
            return [dict(r) for r in rows]
        
        @self.app.post("/guilds/{guild_id}/tickets/categories")
        async def create_ticket_category(guild_id: int, cat: TicketCategoryCreate, auth: bool = Depends(self._verify_api_key)):
            await self.bot.db.execute(
                """
                INSERT INTO ticket_categories (guild_id, name, emoji)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, name) DO UPDATE SET emoji = EXCLUDED.emoji
                """,
                guild_id, cat.name, cat.emoji
            )
            return {"success": True, "name": cat.name}
        
        @self.app.post("/guilds/{guild_id}/tickets/create")
        async def create_ticket(guild_id: int, ticket: TicketCreate, auth: bool = Depends(self._verify_api_key)):
            """Crea un ticket simulando a un cliente."""
            import discord
            from datetime import datetime
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            user = guild.get_member(ticket.user_id)
            if not user:
                raise HTTPException(404, "User not found in guild")
            
            # Crear canal privado
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }
            
            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{user.name}",
                overwrites=overwrites
            )
            
            # Guardar en BD
            await self.bot.db.execute(
                """
                INSERT INTO tickets (guild_id, channel_id, user_id, category_id, priority)
                VALUES ($1, $2, $3, $4, $5)
                """,
                guild_id, ticket_channel.id, user.id, ticket.category_id, ticket.priority
            )
            
            # Enviar mensaje inicial
            emoji = "🔴" if ticket.priority == "urgente" else "🟢"
            embed = discord.Embed(
                title=f"{emoji} Ticket Abierto via API",
                description=ticket.description,
                color=discord.Color.red() if ticket.priority == "urgente" else discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Usuario", value=user.mention)
            embed.add_field(name="Prioridad", value=ticket.priority.title())
            embed.set_footer(text="Un moderador te atenderá pronto")
            
            await ticket_channel.send(embed=embed)
            await ticket_channel.send(f"{user.mention}, tu ticket ha sido creado.")
            
            return {
                "success": True, 
                "channel_id": ticket_channel.id,
                "channel_name": ticket_channel.name,
                "user": str(user)
            }
        
        @self.app.delete("/guilds/{guild_id}/tickets/{channel_id}")
        async def close_ticket(guild_id: int, channel_id: int, auth: bool = Depends(self._verify_api_key)):
            """Cierra y elimina un ticket."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.delete(reason="Ticket cerrado via API")
            
            # Actualizar BD
            await self.bot.db.execute(
                "UPDATE tickets SET status = 'closed', closed_at = NOW() WHERE channel_id = $1",
                channel_id
            )
            
            return {"success": True, "message": "Ticket closed and channel deleted"}
        
        # ==================== SOCIALS ====================
        
        @self.app.post("/guilds/{guild_id}/socials/add")
        async def add_social_feed(guild_id: int, feed: SocialFeed, auth: bool = Depends(self._verify_api_key)):
            """Add a Twitch or YouTube feed."""
            await self.bot.db.execute(
                """
                INSERT INTO social_feeds (guild_id, platform, channel_id, discord_channel_id, custom_message)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, platform, channel_id) DO UPDATE SET 
                    discord_channel_id = EXCLUDED.discord_channel_id,
                    custom_message = EXCLUDED.custom_message
                """,
                guild_id, feed.platform.lower(), feed.username.lower(), feed.channel_id, feed.message
            )
            return {"success": True, "platform": feed.platform, "username": feed.username}
        
        @self.app.get("/guilds/{guild_id}/socials")
        async def list_social_feeds(guild_id: int, auth: bool = Depends(self._verify_api_key)):
            """List all social feeds for a guild."""
            feeds = await self.bot.db.fetch(
                "SELECT platform, channel_id, discord_channel_id, custom_message FROM social_feeds WHERE guild_id = $1",
                guild_id
            )
            return {"feeds": [dict(f) for f in feeds]}
        
        @self.app.delete("/guilds/{guild_id}/socials/{platform}/{username}")
        async def remove_social_feed(guild_id: int, platform: str, username: str, auth: bool = Depends(self._verify_api_key)):
            """Remove a social feed."""
            await self.bot.db.execute(
                "DELETE FROM social_feeds WHERE guild_id = $1 AND platform = $2 AND channel_id = $3",
                guild_id, platform.lower(), username.lower()
            )
            return {"success": True, "removed": username}
        
        @self.app.post("/guilds/{guild_id}/socials/test")
        async def test_social_notification(guild_id: int, test: SocialTest, auth: bool = Depends(self._verify_api_key)):
            """Send a test social notification."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            channel = guild.get_channel(test.channel_id)
            if not channel:
                raise HTTPException(404, "Channel not found")
            
            if test.platform.lower() == "twitch":
                embed = discord.Embed(
                    title=f"🔴 {test.username} is LIVE! (TEST)",
                    description="This is a test notification",
                    url=f"https://twitch.tv/{test.username}",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Playing", value="Test Game")
                embed.add_field(name="Viewers", value="123")
            else:
                embed = discord.Embed(
                    title=f"📺 {test.username} uploaded a video! (TEST)",
                    description="This is a test notification",
                    url=f"https://youtube.com/@{test.username}",
                    color=discord.Color.red()
                )
            
            await channel.send(embed=embed)
            return {"success": True, "message": f"Test notification sent to {channel.name}"}
        
        # ==================== HUB ====================
        
        @self.app.post("/guilds/{guild_id}/hub/test")
        async def test_hub_create(guild_id: int, user_id: int, room_name: str = "Test Room", auth: bool = Depends(self._verify_api_key)):
            """Create a test temporary voice room."""
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise HTTPException(404, "Guild not found")
            
            user = guild.get_member(user_id)
            if not user:
                raise HTTPException(404, "User not found")
            
            config = await self.bot.db.fetchrow(
                "SELECT hub_category_id FROM guild_config WHERE guild_id = $1",
                guild_id
            )
            
            if not config or not config['hub_category_id']:
                raise HTTPException(400, "Hub not configured. Use /hub setup first")
            
            category = guild.get_channel(config['hub_category_id'])
            if not category:
                raise HTTPException(404, "Hub category not found")
            
            channel = await guild.create_voice_channel(
                name=room_name,
                category=category
            )
            
            await channel.set_permissions(user, manage_channels=True, connect=True)
            
            await self.bot.db.execute(
                "INSERT INTO temp_channels (channel_id, guild_id, owner_id) VALUES ($1, $2, $3)",
                channel.id, guild_id, user_id
            )
            
            return {"success": True, "channel_id": channel.id, "channel_name": channel.name, "owner": str(user)}
    
    async def start(self, host: str = "0.0.0.0", port: int = 7000):
        """Inicia el servidor API."""
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
