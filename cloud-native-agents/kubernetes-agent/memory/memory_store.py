# memory/memory_store.py

from typing import Optional
import yaml
import qdrant_client
from qdrant_client.models import VectorParams
from utils.embedding_client import EmbeddingClient  # Assuming you have this ready
from qdrant_client.http.models import Filter, SearchParams

class MemoryStore:
    """Abstraction for long-term vector memory (Qdrant)"""

    def __init__(self, config_path="configs/memory_config.yaml"):
        config = self._load_config(config_path)
        memory_config = config.get("memory", {}).get("long_term", {})

        self.collection_name = memory_config.get("collection_name", "kubernetes-agent-knowledge")

        self.qdrant_client = qdrant_client.QdrantClient(
            host=memory_config.get("host", "localhost"),
            port=memory_config.get("port", 6333)
        )

        self.embedding_client = EmbeddingClient()

        # FIXED: Correct vector dimensions based on the actual embedding size (384)
        VECTOR_SIZE = 384  # Changed from 1536 to 384 to match the embedding

        # Ensure collection exists with the correct vector dimensions
        if self.qdrant_client.collection_exists(self.collection_name):
            # If collection exists but has wrong dimension, recreate it
            try:
                info = self.qdrant_client.get_collection(self.collection_name)
                current_dim = info.config.params.vectors.size
                if current_dim != VECTOR_SIZE:
                    print(f"⚠️ Recreating collection: dimension mismatch (current: {current_dim}, needed: {VECTOR_SIZE})")
                    self.qdrant_client.delete_collection(self.collection_name)
                    self._create_collection(VECTOR_SIZE)
            except Exception as e:
                print(f"Error checking collection dimensions: {e}")
                self._create_collection(VECTOR_SIZE)
        else:
            self._create_collection(VECTOR_SIZE)

    def _create_collection(self, vector_size):
        """Helper method to create a collection with the specified vector size"""
        self.qdrant_client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance="Cosine")
        )
        print(f"✅ Created collection '{self.collection_name}' with vector size {vector_size}")

    def _load_config(self, path):
        with open(path, "r") as f:
            return yaml.safe_load(f)
        
    async def query(self, query_text: str, top_k: int = 5, min_score: float = 0.5, namespace: str = "reflections") -> list:
        """
        Search Qdrant using semantic similarity against existing memory.
        """
        query_vector = await self.embedding_client.generate_embedding(query_text)

        results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=Filter(
                must=[
                    {"key": "namespace", "match": {"value": namespace}}
                ]
            ),
            search_params=SearchParams(hnsw_ef=128, exact=False)
        )

        matches = []
        for result in results:
            payload = result.payload or {}
            score = result.score
            if score >= min_score:
                matches.append({
                    "id": result.id,
                    "score": score,
                    **payload
                })

        return matches

    async def store_long_term_memory(self, content: dict, namespace: str):
        """Store a memory document into Qdrant."""
        # Get the embedding with proper await
        vector = await self.embedding_client.generate_embedding(content.get("goal") or str(content))
        
        # Debug info
        print(f"✓ Generated embedding with dimension: {len(vector)}")
        
        payload = {
            "namespace": namespace,
            **content
        }

        # Skip storage if plan_id is missing (prevent errors)
        if not content.get("plan_id"):
            print("⚠️ Warning: Missing plan_id in content, using a placeholder")
            point_id = f"temp-{hash(str(content))}"
        else:
            point_id = content.get("plan_id")

        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=[{
                "id": point_id,
                "payload": payload,
                "vector": vector
            }]
        )
        
        print(f"✅ Memory stored with id: {point_id}")


# Singleton instance
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store