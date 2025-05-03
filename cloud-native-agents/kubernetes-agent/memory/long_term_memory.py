# memory/long_term_memory.py

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
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
            "goal": plan_response.get("goal"),
            "goal_category": plan_response.get("goal_category", "general"),
            "conversation_id": plan_response.get("conversation_id")
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
            "goal": plan.get("goal"),
            "goal_category": plan.get("goal_category", "general"),
            "conversation_id": plan.get("conversation_id")
        }

        # Added await here to properly wait for the async method
        await self.memory_store.store_long_term_memory(
            content=summary_record,
            namespace="plan_summaries"
        )

        print(f"✅ Plan summary stored into long-term memory for session {session_id}")
        
    async def query_conversations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for previous conversations matching a query.
        
        Args:
            query: The search query text
            limit: Maximum number of results to return
            
        Returns:
            List of matching conversation summaries
        """
        # Use the existing memory_store.query method instead of search_long_term_memory
        results = await self.memory_store.query(
            query_text=query, 
            top_k=limit,
            namespace="plan_summaries"
        )
        
        return results

    async def retrieve_conversation_by_id(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get a specific conversation by ID.
        
        Args:
            conversation_id: The conversation ID to retrieve
            
        Returns:
            Conversation data or None if not found
        """
        # We need to use a semantic query here since memory_store doesn't support exact filters
        # We can query with the conversation ID and then filter results
        results = await self.memory_store.query(
            query_text=f"Conversation ID: {conversation_id}",
            top_k=10,
            namespace="plan_summaries"
        )
        
        # Filter the results to find the exact conversation ID
        for result in results:
            if result.get("conversation_id") == conversation_id:
                return result
                
        return None

    async def retrieve_similar_conversations(self, goal: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find conversations with similar goals.
        
        Args:
            goal: The current goal text
            limit: Maximum number of results to return
            
        Returns:
            List of similar conversation summaries
        """
        results = await self.memory_store.query(
            query_text=goal,
            top_k=limit,
            namespace="plan_summaries"
        )
        
        return results

    async def get_previous_plans_for_goal_category(self, goal_category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find previous plans in the same category.
        
        Args:
            goal_category: The goal category (e.g., "kubernetes", "general")
            limit: Maximum number of results to return
            
        Returns:
            List of previous plans in the category
        """
        # We need to query with the category text and then filter results
        results = await self.memory_store.query(
            query_text=f"Category: {goal_category}",
            top_k=limit * 3,  # Get more results to filter from
            namespace="plan_summaries"
        )
        
        # Filter results to match the exact category
        filtered_results = [
            result for result in results 
            if result.get("goal_category") == goal_category
        ]
        
        # Return only the requested limit
        return filtered_results[:limit]
        
    async def get_task_history(self, task_description: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find previous similar tasks across all conversations.
        
        Args:
            task_description: Description of the current task
            limit: Maximum number of results to return
            
        Returns:
            List of previous similar tasks
        """
        # Search for similar tasks embedded in plan summaries
        results = await self.memory_store.query(
            query_text=task_description,
            top_k=limit,
            namespace="plan_summaries"
        )
        
        # Extract just the task data from the results
        task_history = []
        for result in results:
            # Look through the tasks in each plan summary
            for task in result.get("tasks", []):
                # Calculate similarity score based on the result score
                similarity_score = result.get("score", 0.5)  # Default to 0.5 if no score
                task["similarity_score"] = similarity_score
                task["source_conversation_id"] = result.get("conversation_id")
                task["source_plan_id"] = result.get("plan_id")
                task_history.append(task)
        
        # Sort by similarity score
        task_history.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        # Return top results
        return task_history[:limit]

# Singleton instance
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory