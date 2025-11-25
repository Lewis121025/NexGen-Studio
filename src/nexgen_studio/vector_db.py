"""Vector database integration for embeddings and semantic search."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


@dataclass
class EmbeddingVector:
    """Represents an embedding vector with metadata."""
    
    id: str
    vector: list[float]
    metadata: dict[str, Any]
    text: str
    created_at: datetime
    expires_at: datetime | None = None


class VectorDBProvider(Protocol):
    """Protocol for vector database providers."""
    
    async def insert(self, collection: str, vectors: list[EmbeddingVector]) -> bool:
        """Insert vectors into a collection."""
        ...
    
    async def search(
        self, 
        collection: str, 
        query_vector: list[float], 
        limit: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[EmbeddingVector, float]]:
        """Search for similar vectors. Returns (vector, similarity_score) tuples."""
        ...
    
    async def delete(self, collection: str, vector_ids: list[str]) -> bool:
        """Delete vectors by ID."""
        ...
    
    async def create_collection(self, collection: str, dimension: int) -> bool:
        """Create a new collection."""
        ...
    
    async def cleanup_expired(self, collection: str) -> int:
        """Remove expired vectors. Returns count of deleted vectors."""
        ...


class WeaviateProvider:
    """Weaviate vector database integration."""
    
    def __init__(self, url: str, api_key: str | None = None):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        if api_key:
            self.client.headers["Authorization"] = f"Bearer {api_key}"
    
    async def insert(self, collection: str, vectors: list[EmbeddingVector]) -> bool:
        """Insert vectors into Weaviate."""
        try:
            objects = []
            for vec in vectors:
                obj = {
                    "class": collection,
                    "id": vec.id,
                    "properties": {
                        "text": vec.text,
                        "metadata": vec.metadata,
                        "created_at": vec.created_at.isoformat(),
                        "expires_at": vec.expires_at.isoformat() if vec.expires_at else None,
                    },
                    "vector": vec.vector,
                }
                objects.append(obj)
            
            response = await self.client.post(
                f"{self.url}/v1/batch/objects",
                json={"objects": objects}
            )
            response.raise_for_status()
            logger.info(f"Inserted {len(vectors)} vectors into {collection}")
            return True
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            return False
    
    async def search(
        self, 
        collection: str, 
        query_vector: list[float], 
        limit: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[EmbeddingVector, float]]:
        """Search Weaviate for similar vectors."""
        try:
            query = {
                "vector": query_vector,
                "limit": limit,
            }
            
            if filters:
                query["where"] = self._build_where_filter(filters)
            
            response = await self.client.post(
                f"{self.url}/v1/graphql",
                json={
                    "query": f"""
                    {{
                        Get {{
                            {collection}(nearVector: {query}) {{
                                text
                                metadata
                                created_at
                                expires_at
                                _additional {{
                                    id
                                    distance
                                }}
                            }}
                        }}
                    }}
                    """
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("data", {}).get("Get", {}).get(collection, []):
                vec = EmbeddingVector(
                    id=item["_additional"]["id"],
                    vector=[],  # Not returned in search
                    metadata=item.get("metadata", {}),
                    text=item["text"],
                    created_at=datetime.fromisoformat(item["created_at"]),
                    expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                )
                # Convert distance to similarity (0=identical, 2=opposite)
                similarity = 1.0 - (item["_additional"]["distance"] / 2.0)
                results.append((vec, similarity))
            
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def delete(self, collection: str, vector_ids: list[str]) -> bool:
        """Delete vectors from Weaviate."""
        try:
            for vid in vector_ids:
                response = await self.client.delete(
                    f"{self.url}/v1/objects/{collection}/{vid}"
                )
                response.raise_for_status()
            logger.info(f"Deleted {len(vector_ids)} vectors from {collection}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    async def create_collection(self, collection: str, dimension: int) -> bool:
        """Create a Weaviate class (collection)."""
        try:
            schema = {
                "class": collection,
                "vectorizer": "none",
                "vectorIndexConfig": {
                    "distance": "cosine",
                },
                "properties": [
                    {"name": "text", "dataType": ["text"]},
                    {"name": "metadata", "dataType": ["object"]},
                    {"name": "created_at", "dataType": ["date"]},
                    {"name": "expires_at", "dataType": ["date"]},
                ]
            }
            
            response = await self.client.post(
                f"{self.url}/v1/schema",
                json=schema
            )
            response.raise_for_status()
            logger.info(f"Created collection {collection}")
            return True
        except Exception as e:
            logger.warning(f"Collection creation failed (may already exist): {e}")
            return False
    
    async def cleanup_expired(self, collection: str) -> int:
        """Remove expired vectors."""
        try:
            now = datetime.now(timezone.utc)
            # Query for expired items
            response = await self.client.post(
                f"{self.url}/v1/graphql",
                json={
                    "query": f"""
                    {{
                        Get {{
                            {collection}(where: {{
                                path: ["expires_at"],
                                operator: LessThan,
                                valueDate: "{now.isoformat()}"
                            }}) {{
                                _additional {{
                                    id
                                }}
                            }}
                        }}
                    }}
                    """
                }
            )
            data = response.json()
            items = data.get("data", {}).get("Get", {}).get(collection, [])
            
            if items:
                ids = [item["_additional"]["id"] for item in items]
                await self.delete(collection, ids)
                return len(ids)
            return 0
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
    
    def _build_where_filter(self, filters: dict[str, Any]) -> dict:
        """Build Weaviate where filter from dict."""
        # Simplified filter builder
        conditions = []
        for key, value in filters.items():
            conditions.append({
                "path": [key],
                "operator": "Equal",
                "valueString": str(value)
            })
        
        if len(conditions) == 1:
            return conditions[0]
        
        return {
            "operator": "And",
            "operands": conditions
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class InMemoryVectorDB:
    """In-memory vector database for development/testing."""
    
    def __init__(self):
        self.collections: dict[str, list[EmbeddingVector]] = {}
    
    async def insert(self, collection: str, vectors: list[EmbeddingVector]) -> bool:
        """Insert vectors into memory."""
        if collection not in self.collections:
            self.collections[collection] = []
        self.collections[collection].extend(vectors)
        logger.debug(f"Inserted {len(vectors)} vectors into {collection} (in-memory)")
        return True
    
    async def search(
        self, 
        collection: str, 
        query_vector: list[float], 
        limit: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[EmbeddingVector, float]]:
        """Search using cosine similarity."""
        if collection not in self.collections:
            return []
        
        results = []
        for vec in self.collections[collection]:
            # Apply filters
            if filters:
                match = all(vec.metadata.get(k) == v for k, v in filters.items())
                if not match:
                    continue
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_vector, vec.vector)
            results.append((vec, similarity))
        
        # Sort by similarity and return top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    async def delete(self, collection: str, vector_ids: list[str]) -> bool:
        """Delete vectors from memory."""
        if collection not in self.collections:
            return False
        
        self.collections[collection] = [
            v for v in self.collections[collection] if v.id not in vector_ids
        ]
        return True
    
    async def create_collection(self, collection: str, dimension: int) -> bool:
        """Create collection in memory."""
        if collection not in self.collections:
            self.collections[collection] = []
        return True
    
    async def cleanup_expired(self, collection: str) -> int:
        """Remove expired vectors."""
        if collection not in self.collections:
            return 0
        
        now = datetime.now(timezone.utc)
        before = len(self.collections[collection])
        self.collections[collection] = [
            v for v in self.collections[collection]
            if not v.expires_at or v.expires_at > now
        ]
        return before - len(self.collections[collection])
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)
    
    async def close(self):
        """No-op for in-memory."""
        pass


class VectorDBManager:
    """Manages vector database connections and operations."""
    
    def __init__(self):
        self.provider: VectorDBProvider | None = None
        self._initialized = False
    
    def initialize(self):
        """Initialize vector DB based on settings."""
        if self._initialized:
            return
        
        if settings.vector_db_type == "weaviate":
            if not settings.vector_db_url:
                logger.warning("Weaviate URL not configured, using in-memory vector DB")
                self.provider = InMemoryVectorDB()
            else:
                self.provider = WeaviateProvider(
                    settings.vector_db_url,
                    settings.vector_db_api_key
                )
                logger.info("Initialized Weaviate vector database")
        else:
            self.provider = InMemoryVectorDB()
            logger.info("Using in-memory vector database")
        
        self._initialized = True
    
    async def store_conversation_memory(
        self,
        session_id: str,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any],
        ttl_days: int = 30
    ) -> bool:
        """Store conversation memory with TTL."""
        if not self.provider:
            self.initialize()
        
        vec = EmbeddingVector(
            id=hashlib.sha256(f"{session_id}:{text}".encode()).hexdigest(),
            vector=embedding,
            metadata={**metadata, "session_id": session_id},
            text=text,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days)
        )
        
        return await self.provider.insert("ConversationMemory", [vec])
    
    async def search_memories(
        self,
        query_embedding: list[float],
        user_id: str | None = None,
        limit: int = 5
    ) -> list[tuple[str, float, dict]]:
        """Search for relevant conversation memories."""
        if not self.provider:
            self.initialize()
        
        filters = {"user_id": user_id} if user_id else None
        results = await self.provider.search(
            "ConversationMemory",
            query_embedding,
            limit=limit,
            filters=filters
        )
        
        return [(vec.text, score, vec.metadata) for vec, score in results]
    
    async def cleanup_old_memories(self) -> int:
        """Remove expired memories."""
        if not self.provider:
            return 0
        
        count = await self.provider.cleanup_expired("ConversationMemory")
        logger.info(f"Cleaned up {count} expired memories")
        return count
    
    async def close(self):
        """Close vector DB connections."""
        if self.provider:
            await self.provider.close()


# Global instance
vector_db = VectorDBManager()
