"""
Lycan AI - Retrieval Engine
Time-weighted semantic search in ChromaDB.
"""

import chromadb
import os
from datetime import datetime
from typing import Optional
import json


CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/data/chroma_db")

# Time-weighting parameters
ALPHA = 0.7  # Weight for semantic similarity
BETA = 0.3   # Weight for temporal freshness


class RetrievalEngine:
    """Semantic search with time-weighting for relevant memory retrieval."""
    
    def __init__(self):
        # New ChromaDB API
        self.chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        
        self.collection = self.chroma.get_or_create_collection(
            name="lycan_memory",
            metadata={"hnsw:space": "cosine"}
        )
    
    def _calculate_freshness(self, timestamp: int) -> float:
        """Calculate temporal freshness score (0-1, higher = more recent)."""
        now = datetime.utcnow().timestamp()
        age_seconds = now - timestamp
        
        # Decay function: 1 / (1 + age_in_days)
        age_days = age_seconds / 86400
        freshness = 1 / (1 + age_days)
        
        return freshness
    
    def _rerank_with_time_weight(self, results: dict) -> list:
        """Apply time-weighting formula to rerank results."""
        if not results or not results.get("documents"):
            return []
        
        reranked = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)
        distances = results["distances"][0] if results.get("distances") else [0] * len(documents)
        
        for i, doc in enumerate(documents):
            meta = metadatas[i]
            distance = distances[i]
            
            # Convert distance to similarity (ChromaDB uses L2 or cosine distance)
            similarity = 1 - min(distance, 1)  # Normalize to 0-1
            
            # Get timestamp and calculate freshness
            timestamp = int(meta.get("timestamp", 0))
            freshness = self._calculate_freshness(timestamp)
            
            # Apply time-weighting formula
            final_score = (similarity * ALPHA) + (freshness * BETA)
            
            reranked.append({
                "summary": doc,
                "timestamp": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
                "topics": meta.get("topics", "").split(","),
                "facts": json.loads(meta.get("facts", "[]")),
                "similarity": similarity,
                "freshness": freshness,
                "score": final_score
            })
        
        # Sort by final score (descending)
        reranked.sort(key=lambda x: x["score"], reverse=True)
        
        return reranked
    
    async def search(self, query: str, guild_id: int, limit: int = 5) -> list:
        """Search for relevant memories with time-weighting."""
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[query],
            n_results=limit * 2,  # Get more for reranking
            where={"guild_id": str(guild_id)},
            include=["documents", "metadatas", "distances"]
        )
        
        # Rerank with time-weighting
        reranked = self._rerank_with_time_weight(results)
        
        # Return top results
        return reranked[:limit]
    
    async def detect_ambiguity(self, query: str, guild_id: int) -> Optional[list]:
        """Detect if there are multiple similar memories that could be confused."""
        results = await self.search(query, guild_id, limit=5)
        
        if len(results) < 2:
            return None
        
        # Check if top 2 results are very similar in score but different in content
        if abs(results[0]["score"] - results[1]["score"]) < 0.1:
            # Ambiguity detected - topics are different
            if results[0]["topics"] != results[1]["topics"]:
                return results[:2]
        
        return None
