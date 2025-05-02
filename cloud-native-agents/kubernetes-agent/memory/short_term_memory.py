# memory/short_term_memory.py

import redis
import json
import yaml
from datetime import datetime, timezone

class ShortTermMemory:
    """Handles short-term conversation/session memory via Redis."""

    def __init__(self, config_path="configs/memory_config.yaml"):
        config = self._load_config(config_path)
        memory_config = config.get("memory", {}).get("short_term", {})

        self.namespace = memory_config.get("namespace", "default-session")
        self.ttl = memory_config.get("ttl", 3600)

        self.redis_client = redis.Redis(
            host=memory_config.get("host", "localhost"),
            port=memory_config.get("port", 6379),
            decode_responses=True
        )

    def _load_config(self, path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def start_session(self) -> str:
        """Create a new session (UUID)."""
        import uuid
        session_id = f"{str(uuid.uuid4())}"
        self.redis_client.hset(session_id, mapping={"context": json.dumps([])})
        self.redis_client.expire(session_id, self.ttl)
        return session_id

    def get_context(self, session_id: str) -> list:
        """Retrieve session context."""
        raw_context = self.redis_client.hget(session_id, "context")
        return json.loads(raw_context) if raw_context else []

    def update_context(self, session_id: str, task: dict, feedback: dict = None):
        """Update session context after a task execution."""
        current_context = self.get_context(session_id)

        task_summary = {
            "task_id": task.get("id"),
            "description": task.get("description"),
            "execution_status": "completed",
            "feedback_result": feedback.get("feedback_result") if feedback else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        current_context.append(task_summary)

        self.redis_client.hset(session_id, mapping={"context": json.dumps(current_context)})
        self.redis_client.expire(session_id, self.ttl)  # refresh TTL after each update
