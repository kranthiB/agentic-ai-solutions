# services/conversation/conversation_service.py
import redis
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

class ConversationService:
    """
    Service for managing conversations with the Kubernetes AI Agent
    
    This service uses Redis as a simple store for conversation data, but
    could be extended to use a more robust database in production.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize the conversation service with Redis connection"""
        self.redis = redis.from_url(redis_url)
        logger.info("ConversationService initialized with Redis connection")
    
    async def create_conversation(
        self, 
        conversation_id: str, 
        user_id: str, 
        goal: str, 
        goal_category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation
        
        Args:
            conversation_id: Unique identifier for the conversation
            user_id: ID of the user who created the conversation
            goal: The user's goal or query
            goal_category: Category of the goal (general, kubernetes, etc.)
            metadata: Optional additional data
            
        Returns:
            Dict containing the created conversation data
        """
        now = datetime.now().isoformat()
        
        # Prepare conversation data
        conversation_data = {
            "id": conversation_id,
            "user_id": user_id,
            "goal": goal,
            "goal_category": goal_category,
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
            "messages": []
        }
        
        # Store in Redis
        conversation_key = f"conversation:{conversation_id}"
        self.redis.hset(conversation_key, "data", json.dumps(conversation_data))
        
        # Add to user's conversations list
        user_conversations_key = f"user:{user_id}:conversations"
        self.redis.zadd(user_conversations_key, {conversation_id: datetime.utcnow().timestamp()})
        
        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        return conversation_data
    
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None):
        """
        Delete a conversation by ID
        
        Args:
            conversation_id: ID of the conversation to delete
            user_id: Optional user ID to verify ownership
            
        Returns:
            None
        """
        conversation_key = f"conversation:{conversation_id}"
        
        # Check if conversation exists
        if not self.redis.exists(conversation_key):
            logger.warning(f"Conversation {conversation_id} not found")
            return
        
        # If user_id provided, verify ownership
        if user_id:
            conversation_json = self.redis.hget(conversation_key, "data")
            if not conversation_json:
                logger.warning(f"Conversation {conversation_id} not found")
                return
            
            conversation = json.loads(conversation_json)
            if conversation.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete conversation {conversation_id} (owned by {conversation.get('user_id')})")
                return
        
        # Delete the conversation
        self.redis.delete(conversation_key)
        
        # Remove from user's conversations list
        if user_id:
            user_conversations_key = f"user:{user_id}:conversations"
            self.redis.zrem(user_conversations_key, conversation_id)
        
        logger.info(f"Deleted conversation {conversation_id}")


    async def get_conversation(
        self, 
        conversation_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID
        
        Args:
            conversation_id: ID of the conversation to retrieve
            user_id: Optional user ID to verify ownership
            
        Returns:
            Conversation data or None if not found
        """
        conversation_key = f"conversation:{conversation_id}"
        conversation_json = self.redis.hget(conversation_key, "data")
        
        if not conversation_json:
            logger.warning(f"Conversation {conversation_id} not found")
            return None
        
        conversation = json.loads(conversation_json)
        
        # If user_id provided, verify ownership
        if user_id and conversation.get("user_id") != user_id:
            logger.warning(f"User {user_id} attempted to access conversation {conversation_id} (owned by {conversation.get('user_id')})")
            return None
        
        return conversation
    
    async def update_conversation_status(
        self,
        conversation_id: str,
        status: str,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update the status of a conversation
        
        Args:
            conversation_id: ID of the conversation to update
            status: New status (created, planning, executing, completed, error)
            error: Optional error message if status is 'error'
            
        Returns:
            Updated conversation data
        """
        # Get current conversation data
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"Cannot update status for non-existent conversation {conversation_id}")
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Update fields
        now = datetime.utcnow().isoformat()
        conversation["status"] = status
        conversation["updated_at"] = now
        
        if status == "error" and error:
            conversation["error"] = error
            
        if status == "completed":
            conversation["completed_at"] = now
        
        # Store updated data
        conversation_key = f"conversation:{conversation_id}"
        self.redis.hset(conversation_key, "data", json.dumps(conversation))
        
        logger.info(f"Updated conversation {conversation_id} status to {status}")
        return conversation
    
    async def list_conversations(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List conversations for a user
        
        Args:
            user_id: ID of the user
            limit: Maximum number of conversations to return
            offset: Pagination offset
            
        Returns:
            List of conversation data objects
        """
        user_conversations_key = f"user:{user_id}:conversations"
        
        # Get conversation IDs sorted by creation time (newest first)
        conversation_ids = self.redis.zrevrange(
            user_conversations_key, 
            offset, 
            offset + limit - 1
        )
        
        results = []
        for conv_id in conversation_ids:
            conv_id_str = conv_id.decode('utf-8') if isinstance(conv_id, bytes) else conv_id
            conversation = await self.get_conversation(conv_id_str)
            if conversation:
                results.append(conversation)
        
        return results
    
    async def add_message(
        self,
        conversation_id: str,
        message_id: str,
        content: str,
        sender: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to a conversation
        
        Args:
            conversation_id: ID of the conversation
            message_id: Unique ID for the message
            content: Message content
            sender: Message sender (user or agent)
            metadata: Optional additional data
            
        Returns:
            Created message data
        """
        # Get current conversation
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"Cannot add message to non-existent conversation {conversation_id}")
            raise ValueError(f"Conversation {conversation_id} not found")
        
        now = datetime.utcnow().isoformat()
        
        # Create message data
        message_data = {
            "id": message_id,
            "conversation_id": conversation_id,
            "content": content,
            "sender": sender,
            "created_at": now,
            "metadata": metadata or {}
        }
        
        # Add to messages list in conversation
        if "messages" not in conversation:
            conversation["messages"] = []
            
        conversation["messages"].append(message_data)
        conversation["updated_at"] = now
        
        # Store updated conversation
        conversation_key = f"conversation:{conversation_id}"
        self.redis.hset(conversation_key, "data", json.dumps(conversation))
        
        # Also store message separately for efficient access
        message_key = f"conversation:{conversation_id}:message:{message_id}"
        self.redis.set(message_key, json.dumps(message_data))
        
        # Add to conversation messages timeline
        messages_timeline_key = f"conversation:{conversation_id}:messages"
        self.redis.zadd(messages_timeline_key, {message_id: datetime.utcnow().timestamp()})
        
        logger.info(f"Added {sender} message {message_id} to conversation {conversation_id}")
        return message_data
        
    async def list_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        before_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List messages in a conversation
        
        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages to return
            before_id: Optional message ID to start pagination
            
        Returns:
            List of message data objects
        """
        messages_timeline_key = f"conversation:{conversation_id}:messages"
        
        # If before_id is provided, get its score (timestamp) for pagination
        max_score = "+inf"
        if before_id:
            score = self.redis.zscore(messages_timeline_key, before_id)
            if score:
                max_score = "(" + str(score)  # Exclusive upper bound
        
        # Get message IDs sorted by creation time (newest first)
        message_ids = self.redis.zrevrangebyscore(
            messages_timeline_key,
            max_score,
            "-inf",
            start=0,
            num=limit
        )
        
        results = []
        for msg_id in message_ids:
            msg_id_str = msg_id.decode('utf-8') if isinstance(msg_id, bytes) else msg_id
            message_key = f"conversation:{conversation_id}:message:{msg_id_str}"
            message_json = self.redis.get(message_key)
            
            if message_json:
                try:
                    message = json.loads(message_json)
                    results.append(message)
                except json.JSONDecodeError:
                    logger.error(f"Error decoding message {msg_id_str}")
        
        return results
    
    async def get_conversation_status(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get detailed status information about a conversation
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Status information including progress, current tasks, etc.
        """
        # Get conversation data
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"Cannot get status for non-existent conversation {conversation_id}")
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Get plan status from Redis if available
        plan_key = f"conversation:{conversation_id}:plan"
        plan_json = self.redis.get(plan_key)
        plan_data = json.loads(plan_json) if plan_json else {}
        
        # Build status response
        status_data = {
            "conversation_id": conversation_id,
            "status": conversation.get("status", "unknown"),
            "started_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "completed_at": conversation.get("completed_at"),
            "error": conversation.get("error")
        }
        
        # Add plan-specific data if available
        if plan_data:
            tasks_completed = sum(1 for t in plan_data.get("tasks", []) 
                              if t.get("status") == "completed")
            total_tasks = len(plan_data.get("tasks", []))
            
            # Find current task
            current_task = None
            for task in plan_data.get("tasks", []):
                if task.get("status") == "in_progress":
                    current_task = task.get("description", "Unknown task")
                    break
                    
            # Calculate progress percentage
            progress = (tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
            
            # Add to status data
            status_data.update({
                "current_task": current_task,
                "tasks_completed": tasks_completed,
                "total_tasks": total_tasks,
                "progress_percentage": progress,
                "plan_id": plan_data.get("plan_id")
            })
            
            # Estimate completion time (simple projection based on progress)
            if progress > 0 and conversation.get("created_at"):
                created_time = datetime.fromisoformat(conversation.get("created_at"))
                time_elapsed = (datetime.utcnow() - created_time).total_seconds()
                estimated_total_time = time_elapsed / (progress / 100)
                time_remaining = estimated_total_time - time_elapsed
                
                if time_remaining > 0:
                    estimated_completion = datetime.utcnow() + timedelta(seconds=time_remaining)
                    status_data["estimated_completion"] = estimated_completion.isoformat()
        
        return status_data
    
    async def update_plan_status(
        self, 
        conversation_id: str, 
        plan_id: str, 
        tasks: List[Dict[str, Any]]
    ) -> None:
        """
        Update the plan status for a conversation
        
        Args:
            conversation_id: ID of the conversation
            plan_id: ID of the plan
            tasks: List of tasks with status
        """
        plan_data = {
            "plan_id": plan_id,
            "conversation_id": conversation_id,
            "tasks": tasks,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store plan data
        plan_key = f"conversation:{conversation_id}:plan"
        self.redis.set(plan_key, json.dumps(plan_data))
        
        logger.info(f"Updated plan status for conversation {conversation_id}")
        
    async def update_task_status(
        self,
        conversation_id: str,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update the status of a specific task
        
        Args:
            conversation_id: ID of the conversation
            task_id: ID of the task
            status: New status (pending, in_progress, completed, failed)
            result: Optional result data
        """
        # Get plan data
        plan_key = f"conversation:{conversation_id}:plan"
        plan_json = self.redis.get(plan_key)
        
        if not plan_json:
            logger.error(f"Cannot update task in non-existent plan for conversation {conversation_id}")
            return
            
        plan_data = json.loads(plan_json)
        tasks = plan_data.get("tasks", [])
        
        # Update task status
        for i, task in enumerate(tasks):
            if task.get("id") == task_id:
                tasks[i]["status"] = status
                tasks[i]["updated_at"] = datetime.utcnow().isoformat()
                
                if result:
                    tasks[i]["result"] = result
                
                # Update plan data
                plan_data["tasks"] = tasks
                plan_data["updated_at"] = datetime.utcnow().isoformat()
                
                # Store updated plan
                self.redis.set(plan_key, json.dumps(plan_data))
                
                logger.info(f"Updated task {task_id} status to {status} for conversation {conversation_id}")
                return
        
        logger.warning(f"Task {task_id} not found in plan for conversation {conversation_id}")

# Singleton instance
_conversation_service: Optional[ConversationService] = None

def get_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service