# memory/short_term_memory.py

from typing import Optional
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
        
    def store_message(self, session_id: str, message: dict):
        """
        Store a conversation message in the session context.
        
        Args:
            session_id: The session identifier
            message: Dict containing sender, content, timestamp, etc.
        """
        current_context = self.get_context(session_id)
        
        # Check if we have a messages list already
        has_messages = False
        for item in current_context:
            if item.get("type") == "messages":
                item["data"].append(message)
                has_messages = True
                break
        
        # If no messages list exists, create one
        if not has_messages:
            current_context.append({
                "type": "messages",
                "data": [message]
            })
        
        # Update Redis with the new context
        self.redis_client.hset(session_id, mapping={"context": json.dumps(current_context)})
        self.redis_client.expire(session_id, self.ttl)  # refresh TTL
        
    def get_conversation_messages(self, session_id: str) -> list:
        """
        Get all conversation messages from the session context.
        
        Args:
            session_id: The session identifier
            
        Returns:
            List of message dictionaries
        """
        current_context = self.get_context(session_id)
        
        # Find messages list
        for item in current_context:
            if item.get("type") == "messages":
                return item.get("data", [])
        
        return []  # No messages found

    def store_context_item(self, session_id: str, item_type: str, data: dict):
        """
        Store arbitrary context information by type.
        
        Args:
            session_id: The session identifier
            item_type: Type of context item (e.g., "kb_references", "plans", "definitions")
            data: The context data to store
        """
        current_context = self.get_context(session_id)
        
        # Check if we have this type already
        has_type = False
        for item in current_context:
            if item.get("type") == item_type:
                # For lists, append; for dictionaries, update
                if isinstance(item["data"], list) and isinstance(data, list):
                    item["data"].extend(data)
                elif isinstance(item["data"], dict) and isinstance(data, dict):
                    item["data"].update(data)
                else:
                    # Replace data if types don't match
                    item["data"] = data
                has_type = True
                break
        
        # If type doesn't exist, create it
        if not has_type:
            current_context.append({
                "type": item_type,
                "data": data
            })
        
        # Update Redis with the new context
        self.redis_client.hset(session_id, mapping={"context": json.dumps(current_context)})
        self.redis_client.expire(session_id, self.ttl)  # refresh TTL

# Singleton instance
_short_term_memory: Optional[ShortTermMemory] = None

def get_short_term_memory() -> ShortTermMemory:
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory