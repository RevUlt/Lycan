"""
Lycan AI - Actions
Discord actions that Lycan can execute.
"""

import discord
from typing import Optional
import re


class LycanActions:
    """Handles Discord actions that Lycan can perform."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Actions that need confirmation
        self.destructive_actions = ["delete_channel", "delete_role", "kick", "ban"]
    
    async def parse_and_execute(self, content: str, guild: discord.Guild, channel: discord.TextChannel) -> dict:
        """Parse user intent and execute appropriate action."""
        
        lower_content = content.lower()
        
        # Create channel (expanded keywords)
        if any(kw in lower_content for kw in [
            "crea un canal", "create channel", "haz un canal",
            "puedes crear un canal", "crea canal", "nuevo canal"
        ]):
            return await self._create_channel(content, guild)
        
        # Create category (expanded keywords)
        if any(kw in lower_content for kw in [
            "crea una categoría", "create category", "haz una categoría",
            "crea una categoria", "puedes crear una categoría", "nueva categoría"
        ]):
            return await self._create_category(content, guild)
        
        # Create embed (expanded keywords)
        if any(kw in lower_content for kw in [
            "crea un embed", "create embed", "haz un embed",
            "puedes crear un embed", "crear embed", "un embed"
        ]):
            return await self._create_embed(content, channel)
        
        # Review structure (expanded keywords)
        if any(kw in lower_content for kw in [
            "revisa", "review", "analiza", "estructura",
            "muestra los canales", "canales del servidor", "info del servidor"
        ]):
            return await self._analyze_structure(content, guild)
        
        # Delete channel (needs confirmation)
        if any(kw in lower_content for kw in [
            "borra el canal", "delete channel", "elimina el canal",
            "borra canal", "eliminar canal"
        ]):
            return {
                "needs_confirmation": True,
                "action": "delete_channel",
                "description": "Borrar el canal mencionado",
                "params": content
            }
        
        # Unknown action
        return {
            "needs_confirmation": False,
            "action": "unknown",
            "result": "No entendí qué acción realizar. ¿Podrías ser más específico?"
        }
    
    async def _create_channel(self, content: str, guild: discord.Guild) -> dict:
        """Create a text or voice channel."""
        
        # Extract channel name (basic parsing)
        # TODO: Use Gemini for better NLU
        name_match = re.search(r'(?:llamado|called|de nombre|named)\s+["\']?([^"\']+)["\']?', content.lower())
        
        if name_match:
            channel_name = name_match.group(1).strip()
        else:
            # Try to extract after "canal de" or "channel for"
            name_match = re.search(r'(?:canal de|channel for|canal)\s+(\w+)', content.lower())
            channel_name = name_match.group(1) if name_match else "nuevo-canal"
        
        # Determine type
        is_voice = any(kw in content.lower() for kw in ["voz", "voice", "audio"])
        
        try:
            if is_voice:
                new_channel = await guild.create_voice_channel(name=channel_name)
            else:
                new_channel = await guild.create_text_channel(name=channel_name)
            
            return {
                "needs_confirmation": False,
                "action": "create_channel",
                "result": f"✅ Canal {'de voz' if is_voice else 'de texto'} **{channel_name}** creado: {new_channel.mention}"
            }
        except discord.Forbidden:
            return {
                "needs_confirmation": False,
                "action": "create_channel",
                "result": "❌ No tengo permisos para crear canales."
            }
    
    async def _create_category(self, content: str, guild: discord.Guild) -> dict:
        """Create a category."""
        
        name_match = re.search(r'(?:llamada|called|de nombre|named)\s+["\']?([^"\']+)["\']?', content.lower())
        
        if name_match:
            category_name = name_match.group(1).strip()
        else:
            name_match = re.search(r'(?:categoría de|category for|categoría)\s+(\w+)', content.lower())
            category_name = name_match.group(1) if name_match else "Nueva Categoría"
        
        try:
            new_category = await guild.create_category(name=category_name)
            
            return {
                "needs_confirmation": False,
                "action": "create_category",
                "result": f"✅ Categoría **{category_name}** creada."
            }
        except discord.Forbidden:
            return {
                "needs_confirmation": False,
                "action": "create_category",
                "result": "❌ No tengo permisos para crear categorías."
            }
    
    async def _create_embed(self, content: str, channel: discord.TextChannel) -> dict:
        """Create an embed in the channel."""
        
        # For now, create a basic embed
        # TODO: Use Gemini to parse the full embed content
        
        embed = discord.Embed(
            title="Embed creado por Lycan",
            description="Este es un embed de prueba. Puedo personalizarlo si me dices qué quieres.",
            color=0x3498DB
        )
        embed.set_footer(text="Lycan AI")
        
        await channel.send(embed=embed)
        
        return {
            "needs_confirmation": False,
            "action": "create_embed",
            "result": "✅ Embed creado. ¿Quieres que lo modifique?"
        }
    
    async def _analyze_structure(self, content: str, guild: discord.Guild) -> dict:
        """Analyze server structure and provide recommendations."""
        
        categories = guild.categories
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
        roles = guild.roles
        
        analysis = f"""**Análisis del servidor {guild.name}:**

📁 **Categorías:** {len(categories)}
{chr(10).join([f'  • {cat.name} ({len(cat.channels)} canales)' for cat in categories[:10]])}

📝 **Canales de texto:** {len(text_channels)}
🔊 **Canales de voz:** {len(voice_channels)}
🎭 **Roles:** {len(roles)}

¿Quieres que analice algo específico o te de recomendaciones?"""
        
        return {
            "needs_confirmation": False,
            "action": "analyze",
            "result": analysis
        }
    
    async def confirm_action(self, action: str, params: str, guild: discord.Guild) -> dict:
        """Execute a confirmed destructive action."""
        
        if action == "delete_channel":
            # Find channel by name or mention
            channel_match = re.search(r'<#(\d+)>', params)
            if channel_match:
                channel = guild.get_channel(int(channel_match.group(1)))
                if channel:
                    await channel.delete()
                    return {"result": f"✅ Canal eliminado."}
        
        return {"result": "❌ No pude ejecutar la acción."}
