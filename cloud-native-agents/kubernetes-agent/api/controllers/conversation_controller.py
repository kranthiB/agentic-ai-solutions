# api/controllers/conversation_controller.py
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import List, Optional
import uuid

# Import data models
from api.models.conversation import (
    ConversationCreate, 
    ConversationResponse, 
    MessageCreate,
    MessageResponse,
    ConversationListResponse
)

# Import services
from services.conversation.conversation_service import get_conversation_service
from api.websockets.connection_manager import ConnectionManager

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

# Initialize router
router = APIRouter()

# Initialize services
conversation_service = get_conversation_service()
connection_manager = ConnectionManager()

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation: ConversationCreate,
    background_tasks: BackgroundTasks
):
    """
    Create a new conversation with the Kubernetes AI Agent
    """
    # Generate a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    # Store initial conversation metadata
    new_conversation = await conversation_service.create_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id,
        goal=conversation.goal,
        goal_category=conversation.goal_category
    )
    
    # Start processing in the background
    background_tasks.add_task(
        process_conversation,
        conversation_id,
        conversation.goal,
        conversation.goal_category
    )
    
    return ConversationResponse(
        id=conversation_id,
        goal=conversation.goal,
        goal_category=conversation.goal_category,
        status="processing",
        created_at=new_conversation.get("created_at")
    )

@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 10,
    offset: int = 0
):
    """
    List all conversations for the current user
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    conversations = await conversation_service.list_conversations(
        user_id=fixed_user_id,
        limit=limit,
        offset=offset
    )
    
    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations),
        limit=limit,
        offset=offset
    )

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str
):
    """
    Get details of a specific conversation
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse(**conversation)

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str,
    message: MessageCreate,
    background_tasks: BackgroundTasks
):
    """
    Add a new message to an existing conversation
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    # Verify conversation exists
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Create message
    message_id = str(uuid.uuid4())
    created_message = await conversation_service.add_message(
        conversation_id=conversation_id,
        message_id=message_id,
        content=message.content,
        sender="user"
    )
    
    # Process message in background
    background_tasks.add_task(
        process_message,
        conversation_id,
        message_id,
        message.content
    )
    
    return MessageResponse(
        id=message_id,
        conversation_id=conversation_id,
        content=message.content,
        sender="user",
        created_at=created_message.get("created_at")
    )

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: str,
    limit: int = 50,
    before_id: Optional[str] = None
):
    """
    List all messages in a conversation
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    # Verify conversation exists
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = await conversation_service.list_messages(
        conversation_id=conversation_id,
        limit=limit,
        before_id=before_id
    )
    
    return messages

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str
):
    """
    Delete a conversation
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    # Verify conversation exists
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    await conversation_service.delete_conversation(conversation_id, fixed_user_id)
    
    return {"detail": "Conversation deleted successfully"}

@router.get("/{conversation_id}/status")
async def get_conversation_status(
    conversation_id: str
):
    """
    Get the current status of a conversation
    """
    # For now, use a fixed user ID until auth is implemented
    fixed_user_id = "temp-user-id"
    
    # Verify conversation exists
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=fixed_user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    status_details = await conversation_service.get_conversation_status(
        conversation_id=conversation_id
    )
    
    return status_details

async def process_conversation(conversation_id: str, goal: str, goal_category: str):
    """
    Background task to process a conversation
    """
    try:
        logger.info(f"Processing conversation {conversation_id} with goal: {goal}")
        
        # Notify clients that agent is thinking
        await connection_manager.broadcast_agent_thinking(conversation_id, True)
        
        # Update conversation status
        await conversation_service.update_conversation_status(
            conversation_id=conversation_id,
            status="planning"
        )
        
        # Import here to avoid circular imports
        from core.conversation_manager_api import get_conversation_manager_api
        
        # Create conversation manager
        manager = get_conversation_manager_api()
        
        # Run conversation (this will take time)
        result = await manager.run_conversation(goal, goal_category, conversation_id)
        
        # Add agent response as a message
        message_id = str(uuid.uuid4())
        await conversation_service.add_message(
            conversation_id=conversation_id,
            message_id=message_id,
            content=result,
            sender="agent"
        )
        
        # Update conversation status
        await conversation_service.update_conversation_status(
            conversation_id=conversation_id,
            status="completed"
        )
        
        # Notify clients that agent is done thinking
        await connection_manager.broadcast_agent_thinking(conversation_id, False)
        
        logger.info(f"Completed processing conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
        
        # Update conversation status to error
        await conversation_service.update_conversation_status(
            conversation_id=conversation_id,
            status="error",
            error=str(e)
        )
        
        # Broadcast error to clients
        await connection_manager.broadcast_error(
            conversation_id=conversation_id,
            error_message=f"Error processing conversation: {str(e)}"
        )

async def process_message(conversation_id: str, message_id: str, content: str):
    """
    Background task to process a message
    """
    try:
        logger.info(f"Processing message {message_id} in conversation {conversation_id}")
        
        # Notify clients that agent is thinking
        await connection_manager.broadcast_agent_thinking(conversation_id, True)
        
        # Import here to avoid circular imports
        from core.conversation_manager_api import get_conversation_manager_api
        
        # Create conversation manager
        manager = get_conversation_manager_api()
        
        # Get conversation details
        conversation = await conversation_service.get_conversation(conversation_id)
        
        # Determine if this is a follow-up question or a new goal
        is_followup = conversation.get("status") == "completed"
        
        if is_followup:
            # Process as a follow-up question
            result = await manager.process_followup(
                conversation_id=conversation_id,
                query=content
            )
        else:
            # This shouldn't normally happen, but handle it gracefully
            logger.warning(f"Received message for conversation in status: {conversation.get('status')}")
            result = "I'm still working on your previous request. Please wait until it's completed."
        
        # Add agent response as a message
        response_id = str(uuid.uuid4())
        await conversation_service.add_message(
            conversation_id=conversation_id,
            message_id=response_id,
            content=result,
            sender="agent"
        )
        
        # Notify clients that agent is done thinking
        await connection_manager.broadcast_agent_thinking(conversation_id, False)
        
        logger.info(f"Completed processing message {message_id}")
        
    except Exception as e:
        logger.error(f"Error processing message {message_id}: {str(e)}")
        
        # Broadcast error to clients
        await connection_manager.broadcast_error(
            conversation_id=conversation_id,
            error_message=f"Error processing message: {str(e)}"
        )