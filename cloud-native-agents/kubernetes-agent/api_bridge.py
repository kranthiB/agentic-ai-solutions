# api_bridge.py
from typing import Dict, List, Any, Optional

from monitoring.agent_logger import get_logger
from api.websockets.connection_manager import get_connection_manager

logger = get_logger(__name__)

connection_manager = get_connection_manager()

async def send_plan_update(conversation_id: str, plan_id: str, tasks: List[Dict[str, Any]]):
    """
    Send plan update to WebSocket clients
    
    Args:
        conversation_id: ID of the conversation
        plan_id: ID of the plan
        tasks: List of tasks in the plan
    """
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
    task_description: str,
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
    if connection_manager:
        await connection_manager.broadcast_task_status(
            conversation_id=conversation_id,
            task_id=task_id,
            task_description=task_description,
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
    task_description: str,
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
        task_description=task_description,
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

async def update_session_state(conversation_id: str, state_update: Dict[str, Any]):
    """
    Update the session state for a conversation
    
    Args:
        conversation_id: ID of the conversation
        state_update: Dictionary of state updates to apply
    """
    if connection_manager:
        await connection_manager.update_session_state(
            conversation_id=conversation_id,
            state_update=state_update
        )
        logger.info(f"Updated session state for conversation {conversation_id}")
    else:
        logger.debug(f"Session state update for {conversation_id} not sent - WebSockets not available")

async def broadcast_progress_update(
    conversation_id: str, 
    progress_type: str, 
    percentage: float,
    current_step: int = None,
    total_steps: int = None,
    step_description: str = None
):
    """
    Broadcast a progress update for long-running operations
    
    Args:
        conversation_id: ID of the conversation
        progress_type: Type of progress (plan, task, analysis)
        percentage: Completion percentage (0-100)
        current_step: Current step number (optional)
        total_steps: Total number of steps (optional)
        step_description: Description of current step (optional)
    """
    if connection_manager:
        await connection_manager.broadcast_progress_update(
            conversation_id=conversation_id,
            progress_type=progress_type,
            percentage=percentage,
            current_step=current_step,
            total_steps=total_steps,
            step_description=step_description
        )
        logger.info(f"Sent progress update ({percentage}%) for conversation {conversation_id}")
    else:
        logger.debug(f"Progress update for {conversation_id} not sent - WebSockets not available")

async def broadcast_conversation_summary_update(conversation_id: str, summary: str):
    """
    Broadcast an updated conversation summary
    
    Args:
        conversation_id: ID of the conversation
        summary: Current conversation summary
    """
    if connection_manager:
        await connection_manager.broadcast_conversation_summary_update(
            conversation_id=conversation_id,
            summary=summary
        )
        logger.info(f"Sent conversation summary update for conversation {conversation_id}")
    else:
        logger.debug(f"Conversation summary update for {conversation_id} not sent - WebSockets not available")

async def broadcast_conversation_context(conversation_id: str, context_items: List[Dict[str, Any]]):
    """
    Broadcast current conversation context items to clients
    
    Args:
        conversation_id: ID of the conversation
        context_items: List of context items with their metadata
    """
    if connection_manager:
        await connection_manager.broadcast_conversation_context(
            conversation_id=conversation_id,
            context_items=context_items
        )
        logger.info(f"Sent conversation context update for conversation {conversation_id}")
    else:
        logger.debug(f"Conversation context update for {conversation_id} not sent - WebSockets not available")