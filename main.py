#!/usr/bin/env python3
"""
Lycan Bot - Entry Point
Bot de Discord con API REST integrada.
"""

import asyncio
from pathlib import Path

from core import LycanBot, Config, setup_logger
from api.server import LycanAPI

# Paths
BASE_PATH = Path(__file__).parent
LOGS_PATH = BASE_PATH / "logs"

async def main():
    # Logger
    logger = setup_logger("LYCAN", LOGS_PATH)
    logger.info("Iniciando Lycan Bot...")
    
    # Config
    try:
        config = Config(BASE_PATH)
        config.validate()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return
    
    # Bot
    bot = LycanBot(config, logger)
    
    # API Server
    api = LycanAPI(bot)
    
    async def run_bot():
        try:
            await bot.start(config.discord_token)
        except KeyboardInterrupt:
            pass
        finally:
            await bot.close()
    
    async def run_api():
        await api.start(port=config.api_port)
    
    # Ejecutar ambos en paralelo
    try:
        await asyncio.gather(
            run_bot(),
            run_api()
        )
    except KeyboardInterrupt:
        logger.info("Apagando...")

if __name__ == "__main__":
    asyncio.run(main())
