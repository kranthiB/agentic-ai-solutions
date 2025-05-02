# api_bridge.py
from typing import Dict, List, Any, Optional

from monitoring.agent_logger import get_logger

logger = get_logger(__name__)

def get_connection_manager():
    """
    Safely import the ConnectionManager
    
    Returns ConnectionManager instance or None if not available
    """
    try:
        from api.websockets.connection_manager import ConnectionManager
        return ConnectionManager()
    except ImportError:
        logger.warning("WebSocket ConnectionManager not available - status updates disabled")
        return None

async def send_plan_update(conversation_id: str, plan_id: str, tasks: List[Dict[str, Any]]):
    """
    Send plan update to WebSocket clients
    
    Args:
        conversation_id: ID of the conversation
        plan_id: ID of the plan
        tasks: List of tasks in the plan
    """
    connection_manager = get_connection_manager()
    if connection_manager:
        await connection_manager.broadcast_plan_update(
            conversation_id=conversation_id,
            plan_id=plan_id,
            tasks=tasks
        )
        logger.info(f"Sent plan update for conversation {conversation_id}, plan {plan_id} with {len(tasks)} tasks")
    else:
        logger.debug(f"Plan update for {conversation_id} not sent - WebSockets not available")

async def send_task_update(
    conversation_id: str, 
    task_id: str, 
    status: str, 
    details: Optional[Dict[str, Any]] = None
):
    """
    Send task status update to WebSocket clients
    
    Args:
        conversation_id: ID of the conversation
        task_id: ID of the task
        status: Current status (pending, in_progress, completed, failed)
        details: Optional additional details
    """
    connection_manager = get_connection_manager()
    if connection_manager:
        await connection_manager.broadcast_task_status(
            conversation_id=conversation_id,
            task_id=task_id,
            status=status,
            details=details or {}
        )
        logger.info(f"Sent task {task_id} status update: {status} for conversation {conversation_id}")
    else:
        logger.debug(f"Task update for {task_id} not sent - WebSockets not available")

async def send_thinking_status(conversation_id: str, is_thinking: bool = True):
    """
    Send agent thinking status to WebSocket clients
    
    Args:
        conversation_id: ID of the conversation
        is_thinking: Whether the agent is thinking
    """
    connection_manager = get_connection_manager()
    if connection_manager:
        await connection_manager.broadcast_agent_thinking(
            conversation_id=conversation_id,
            is_thinking=is_thinking
        )
        logger.info(f"Sent thinking status ({is_thinking}) for conversation {conversation_id}")
    else:
        logger.debug(f"Thinking status for {conversation_id} not sent - WebSockets not available")

async def send_error(conversation_id: str, error_message: str, error_code: str = "error"):
    """
    Send error message to WebSocket clients
    
    Args:
        conversation_id: ID of the conversation
        error_message: Error message text
        error_code: Error code for categorization
    """
    connection_manager = get_connection_manager()
    if connection_manager:
        await connection_manager.broadcast_error(
            conversation_id=conversation_id,
            error_message=error_message,
            error_code=error_code
        )
        logger.info(f"Sent error for conversation {conversation_id}: {error_code}")
    else:
        logger.error(f"Error for {conversation_id} not sent - WebSockets not available: {error_message}")

# Function to update conversation service with task status
async def update_conversation_service_task_status(
    conversation_id: str,
    task_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None
):
    """
    Update task status in the conversation service database
    
    Args:
        conversation_id: ID of the conversation
        task_id: ID of the task
        status: New status (pending, in_progress, completed, failed)
        result: Optional result data
    """
    try:
        from services.conversation.conversation_service import get_conversation_service
        conversation_service = get_conversation_service()
        await conversation_service.update_task_status(
            conversation_id=conversation_id,
            task_id=task_id,
            status=status,
            result=result
        )
        logger.info(f"Updated task {task_id} status in database: {status}")
    except ImportError:
        logger.warning("ConversationService not available - task status not persisted")
    except Exception as e:
        logger.error(f"Error updating task status in database: {str(e)}")

# Consolidated function to handle all updates for a task
async def update_task_progress(
    conversation_id: str,
    task_id: str,
    status: str,
    progress_percentage: float = None,
    result: Optional[Dict[str, Any]] = None
):
    """
    Update task progress - both in database and via WebSockets
    
    Args:
        conversation_id: ID of the conversation
        task_id: ID of the task
        status: New status (pending, in_progress, completed, failed)
        progress_percentage: Optional progress percentage (0-100)
        result: Optional result data
    """
    # Build details for WebSocket update
    details = {
        "status": status,
    }
    
    if progress_percentage is not None:
        details["progress_percentage"] = progress_percentage
        
    if result:
        details["result"] = result
    
    # Update WebSocket clients
    await send_task_update(
        conversation_id=conversation_id,
        task_id=task_id,
        status=status,
        details=details
    )
    
    # Update database
    await update_conversation_service_task_status(
        conversation_id=conversation_id,
        task_id=task_id,
        status=status,
        result=result
    )