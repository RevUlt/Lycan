"""
Lycan Bot - Core Config
Carga configuración de .env y YAML.
Básicamente: centraliza toda la configuración.
"""

import os
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

class Config:
    """Gestiona configuración del bot."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        load_dotenv(base_path / ".env")
        
        # Secretos desde .env
        self.discord_token = os.getenv("DISCORD_TOKEN")
        self.database_url = os.getenv("DATABASE_URL")
        self.api_port = int(os.getenv("API_PORT", 7000))
        self.api_secret_key = os.getenv("API_SECRET_KEY")
        
        # Twitch
        self.twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
        self.twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        
        # YouTube
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        
        # Cargar settings.yaml si existe
        self.settings = self._load_yaml("config/settings.yaml")
    
    def _load_yaml(self, relative_path: str) -> Dict[str, Any]:
        """Carga archivo YAML."""
        path = self.base_path / relative_path
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def validate(self) -> bool:
        """Valida que las variables requeridas existan."""
        if not self.discord_token:
            raise ValueError("DISCORD_TOKEN no configurado en .env")
        if not self.database_url:
            raise ValueError("DATABASE_URL no configurado en .env")
        return True
