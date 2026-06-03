"""
Lycan AI - Memory Manager
Matrioshka memory system with buffer and compression.
"""

import os
import json
from typing import Optional
from datetime import datetime
import chromadb


# Configuration
BUFFER_SIZE = 50  # Messages before compression
CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/data/chroma_db")


class MemoryManager:
    """Manages Lycan's short-term buffer and long-term memory."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # In-memory buffer (per guild)
        self.buffers = {}  # guild_id -> [messages]
        
        # ChromaDB for long-term memory (new API)
        self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        
        # Get or create collection
        self.collection = self.chroma.get_or_create_collection(
            name="lycan_memory",
            metadata={"hnsw:space": "cosine"}
        )
    
    async def get_buffer(self, guild_id: int) -> list:
        """Get current message buffer for a guild."""
        return self.buffers.get(guild_id, [])
    
    async def add_message(self, guild_id: int, author_id: int, content: str, is_bot: bool = False):
        """Add message to the buffer."""
        if guild_id not in self.buffers:
            self.buffers[guild_id] = []
        
        self.buffers[guild_id].append({
            "author_id": author_id,
            "content": content,
            "is_bot": is_bot,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def maybe_compress(self, guild_id: int):
        """Check if buffer needs compression and do it."""
        buffer = self.buffers.get(guild_id, [])
        
        if len(buffer) >= BUFFER_SIZE:
            await self._compress_buffer(guild_id)
    
    async def _compress_buffer(self, guild_id: int):
        """Compress buffer to episodic snapshot and store in ChromaDB."""
        buffer = self.buffers.get(guild_id, [])
        if not buffer:
            return
        
        # Create summary using OpenRouter (same API as main chat)
        import openai
        import os
        import logging
        
        logger = logging.getLogger("LYCAN")
        
        OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not OPENROUTER_API_KEY:
            logger.warning("Cannot compress buffer: OPENROUTER_API_KEY not set")
            return
        
        client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        
        conversation_text = "\n".join([
            f"{'Lycan' if m['is_bot'] else 'Usuario'}: {m['content']}"
            for m in buffer
        ])
        
        summary_prompt = f"""Resume esta conversación en un snapshot episódico.
Extrae:
1. Hechos importantes mencionados
2. Decisiones tomadas
3. Temas principales
4. Cualquier configuración o acción realizada

Conversación:
{conversation_text}

Responde en JSON:
{{"summary": "...", "facts": [...], "topics": [...], "actions": [...]}}"""
        
        try:
            response = client.chat.completions.create(
                model="mistralai/devstral-2512:free",  # Free model
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=512,
                temperature=0.3
            )
            
            summary_text = response.choices[0].message.content.strip()
            
            # Parse summary
            if summary_text.startswith("```json"):
                summary_text = summary_text[7:-3]
            elif summary_text.startswith("```"):
                summary_text = summary_text[3:-3]
            
            summary_data = json.loads(summary_text)
            logger.info(f"Buffer compressed for guild {guild_id}: {len(buffer)} messages -> 1 memory")
            
        except Exception as e:
            logger.error(f"Failed to compress buffer: {e}")
            summary_data = {
                "summary": f"Conversación de {len(buffer)} mensajes (no procesada)",
                "facts": [],
                "topics": [],
                "actions": []
            }
        
        # Store in ChromaDB
        doc_id = f"{guild_id}_{datetime.utcnow().timestamp()}"
        
        self.collection.add(
            ids=[doc_id],
            documents=[summary_data.get("summary", "")],
            metadatas=[{
                "guild_id": str(guild_id),
                "timestamp": int(datetime.utcnow().timestamp()),
                "type": "conversation_summary",
                "topics": ",".join(summary_data.get("topics", [])),
                "facts": json.dumps(summary_data.get("facts", [])),
                "actions": json.dumps(summary_data.get("actions", []))
            }]
        )
        
        # Clear buffer
        self.buffers[guild_id] = []
    
    async def search_memories(self, guild_id: int, query: str, limit: int = 3) -> list:
        """Search for relevant memories."""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"guild_id": str(guild_id)}
        )
        
        memories = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                memories.append({
                    "summary": doc,
                    "timestamp": meta.get("timestamp", 0),
                    "topics": meta.get("topics", "").split(","),
                    "facts": json.loads(meta.get("facts", "[]")),
                })
        
        return memories
