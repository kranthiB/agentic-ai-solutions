# api/models/conversation.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConversationCreate(BaseModel):
    """Schema for creating a new conversation"""
    goal: str = Field(..., description="The user's goal for this conversation")
    goal_category: str = Field("general", description="Category of the goal (e.g., 'general', 'kubernetes', 'cluster')")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata for the conversation")

class ConversationResponse(BaseModel):
    """Schema for conversation response"""
    id: str
    goal: str
    goal_category: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ConversationListResponse(BaseModel):
    """Schema for listing conversations"""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int

class MessageCreate(BaseModel):
    """Schema for creating a new message"""
    content: str = Field(..., description="The content of the message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata for the message")

class MessageResponse(BaseModel):
    """Schema for message response"""
    id: str
    conversation_id: str
    content: str
    sender: str  # "user" or "agent"
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

class ConversationStatusResponse(BaseModel):
    """Schema for conversation status"""
    conversation_id: str
    status: str
    current_task: Optional[str] = None
    tasks_completed: Optional[int] = None
    total_tasks: Optional[int] = None
    progress_percentage: Optional[float] = None
    estimated_completion: Optional[datetime] = None
    started_at: Optional[datetime] = None
    error: Optional[str] = None

# api/models/websocket_message.py
from pydantic import BaseModel
from typing import Dict, Any
import time

class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages"""
    type: str
    conversation_id: str
    content: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)
    
    def to_json(self):
        return self.model_dump_json()