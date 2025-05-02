# api/models/websocket_message.py
from pydantic import BaseModel, Field
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