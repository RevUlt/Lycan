"""
Lycan Bot - Core Bot Class
Clase principal del bot con carga modular de cogs.
Básicamente: el bot en sí.
"""

import discord
from discord.ext import commands
from pathlib import Path
from typing import List
import logging

from .database import Database
from .config import Config

class LycanBot(commands.Bot):
    """Clase principal del bot Lycan."""
    
    def __init__(self, config: Config, logger: logging.Logger):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        intents.reactions = True  # Required for reaction roles
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        self.config = config
        self.logger = logger
        self.db: Database = None
    
    async def setup_hook(self) -> None:
        """Se ejecuta antes de conectar. Inicializa BD y carga módulos."""
        # Conectar a PostgreSQL
        self.db = Database(self.config.database_url)
        await self.db.connect()
        self.logger.info("Conectado a PostgreSQL")
        
        # Cargar módulos
        await self.load_modules()
        
        # Sincronizar slash commands
        await self.tree.sync()
        self.logger.info("Slash commands sincronizados")
    
    async def load_modules(self) -> None:
        """Carga todos los módulos desde la carpeta modules/."""
        modules_path = Path(__file__).parent.parent / "modules"
        loaded = 0
        failed = 0
        
        for module_dir in modules_path.iterdir():
            if module_dir.is_dir() and not module_dir.name.startswith("_"):
                try:
                    await self.load_extension(f"modules.{module_dir.name}")
                    self.logger.info(f"Módulo cargado: {module_dir.name}")
                    loaded += 1
                except Exception as e:
                    self.logger.error(f"Error cargando {module_dir.name}: {e}")
                    failed += 1
        
        self.logger.info(f"Módulos: {loaded} cargados, {failed} fallidos")
    
    async def on_ready(self) -> None:
        """Cuando el bot está listo."""
        self.logger.info(f"Conectado como {self.user} (ID: {self.user.id})")
        self.logger.info(f"En {len(self.guilds)} servidores")
    
    async def close(self) -> None:
        """Cierra conexiones al apagar."""
        if self.db:
            await self.db.disconnect()
            self.logger.info("Desconectado de PostgreSQL")
        await super().close()
