"""
Lycan Bot - Core Database
Pool de conexiones a PostgreSQL con asyncpg.
Básicamente: gestiona la conexión a la base de datos.
"""

import asyncpg
from typing import Optional

class Database:
    """Pool de conexiones a PostgreSQL."""
    
    def __init__(self, url: str):
        self.url = url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Crea el pool de conexiones."""
        self.pool = await asyncpg.create_pool(
            self.url,
            min_size=2,
            max_size=10
        )
    
    async def disconnect(self) -> None:
        """Cierra el pool."""
        if self.pool:
            await self.pool.close()
    
    async def execute(self, query: str, *args) -> str:
        """Ejecuta query sin retorno."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> list:
        """Ejecuta query y retorna múltiples filas."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Ejecuta query y retorna una fila."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Ejecuta query y retorna un valor."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
