"""
Lycan Bot - Core Logger
Sistema de logging centralizado.
"""

import logging
import sys
from pathlib import Path

def setup_logger(name: str = "LYCAN", log_dir: Path = None) -> logging.Logger:
    """
    Configura y retorna el logger principal.
    Básicamente: crea logs en consola y archivo.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Evitar duplicados
    if logger.handlers:
        return logger
    
    # Formato
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Archivo
    if log_dir:
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "bot.log", 
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
