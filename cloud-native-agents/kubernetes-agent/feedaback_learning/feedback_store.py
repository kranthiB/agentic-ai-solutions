# kubernetes_agent/feedback_learning/feedback_store.py
# self.feedback_store.save_feedback(feedback)
                
import redis
import uuid
import yaml
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from feedback_learning.feedback_types import FeedbackResult, FeedbackStorage

from utils.embedding_client import EmbeddingClient  

class FeedbackStore:
    """Handles saving feedback into Redis and/or Qdrant."""

    def __init__(self, config_path="configs/feedback_config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        feedback_config = config.get("feedback", {})
        self.storage_backends = feedback_config.get("store_feedback_in", ["redis"])

        self.embedder = EmbeddingClient()
        
        # Redis connection
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)

        # Qdrant connection
        self.qdrant_client = QdrantClient(host="localhost", port=6333)
        self.qdrant_collection_name = "feedback_memory"  # Collection where feedback vectors will be stored

        # Ensure Qdrant collection exists (you may want to create it manually first)

    def save_feedback(self, feedback: dict):
        """
        Save feedback based on storage backends.

        Args:
            feedback (dict): Feedback dictionary expected to have:
              - plan_id
              - task_id
              - feedback_type
              - feedback_result
              - free_text_feedback (optional)
              - timestamp
        """
        feedback_id = str(uuid.uuid4())
        feedback["feedback_id"] = feedback_id

        # Always add timestamp if missing
        if "timestamp" not in feedback:
            feedback["timestamp"] = datetime.utcnow().isoformat()

        if FeedbackStorage.REDIS.value in self.storage_backends or FeedbackStorage.BOTH.value in self.storage_backends:
            self._save_to_redis(feedback)

        if "free_text_feedback" in feedback and feedback["free_text_feedback"]:
            if FeedbackStorage.QDRANT.value in self.storage_backends or FeedbackStorage.BOTH.value in self.storage_backends:
                self._save_to_qdrant(feedback)

    def _save_to_redis(self, feedback: dict):
        """Store feedback as a simple hash in Redis."""
        key = f"feedback:{feedback['feedback_id']}"

        redis_payload = {
            "plan_id": feedback.get("plan_id") or "",
            "task_id": feedback.get("task_id") or "",
            "feedback_type": feedback.get("feedback_type") or "",
            "feedback_result": feedback.get("feedback_result") or FeedbackResult.UNKNOWN.value,
            "timestamp": feedback.get("timestamp") or "",
            "free_text_feedback": feedback.get("free_text_feedback") or "",
        }

        self.redis_client.hmset(key, redis_payload)

    def _save_to_qdrant(self, feedback: dict):
        """Store free-text feedback as an embedded vector in Qdrant."""
        # Generate embedding (you must implement your own embedding_client)
        embedding_vector = self.embedder.generate_embedding(feedback["free_text_feedback"])

        payload = {
            "plan_id": feedback.get("plan_id"),
            "task_id": feedback.get("task_id"),
            "feedback_result": feedback.get("feedback_result"),
            "timestamp": feedback.get("timestamp"),
            "raw_feedback": feedback.get("free_text_feedback"),
        }

        point = PointStruct(
            id=uuid.uuid4().int >> 64,   # generate large int ID
            vector=embedding_vector,
            payload=payload
        )

        self.qdrant_client.upsert(
            collection_name=self.qdrant_collection_name,
            points=[point]
        )
