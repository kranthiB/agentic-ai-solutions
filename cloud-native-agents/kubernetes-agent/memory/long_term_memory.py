# memory/long_term_memory.py

from datetime import datetime, timezone
from typing import Optional
from memory.memory_store import MemoryStore

class LongTermMemory:
    """Handles long-term knowledge memory using Qdrant."""

    def __init__(self, config_path="configs/memory_config.yaml"):
        self.memory_store = MemoryStore(config_path=config_path)

    async def store_plan_summary_v2(self, plan_response: dict):
        """Store a full plan execution summary."""
        print("plan_response")
        print(plan_response)


        summary_record = {
            "plan_id": plan_response["plan_id"],
            "session_id": plan_response["session_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tasks_completed": len(plan_response.get("tasks", [])),
            "tasks": [
                {
                    "id": task.get("id"),
                    "description": task.get("description"),
                    "response": task.get("response").get("result"),
                    "status": task.get("status"),
                }
                for task in plan_response.get("tasks", [])
            ],
            "goal": plan_response.get("goal")
        }

        await self.memory_store.store_long_term_memory(
            content=summary_record,
            namespace="plan_summaries"
        )

        print(f"✅ Plan summary stored into long-term memory for session {plan_response['session_id']}")

    async def store_plan_summary(self, plan: dict, session_id: str):
        """Store a full plan execution summary."""
        summary_record = {
            "plan_id": plan.get("plan_id"),
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tasks": [
                {
                    "task_id": task.get("id"),
                    "description": task.get("description"),
                    "status": "completed"
                }
                for task in plan.get("tasks", [])
            ],
            "goal": plan.get("goal")
        }

        # Added await here to properly wait for the async method
        await self.memory_store.store_long_term_memory(
            content=summary_record,
            namespace="plan_summaries"
        )

        print(f"✅ Plan summary stored into long-term memory for session {session_id}")


# Singleton instance
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory