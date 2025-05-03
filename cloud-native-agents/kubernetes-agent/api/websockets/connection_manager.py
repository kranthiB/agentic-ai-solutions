# api/websockets/connection_manager.py
from fastapi import WebSocket
from typing import Dict, List, Any, Optional

# Import the WebSocketMessage model
from api.models.websocket_message import WebSocketMessage

from monitoring.agent_logger import get_logger

class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting
    """
    
    def __init__(self):
        # Map conversation_id -> list of connected websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.logger = get_logger(__name__)
        
    async def connect(self, websocket: WebSocket, conversation_id: str):
        """
        Connect a new WebSocket client
        """
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)

        self.logger.info(f"New WebSocket connection for conversation {conversation_id}")
        
        # Send initial connection confirmation
        await self.send_personal_message(
            WebSocketMessage(
                type="connection_established",
                conversation_id=conversation_id,
                content={"status": "connected"}
            ),
            websocket
        )
    
    def disconnect(self, websocket: WebSocket, conversation_id: str):
        """
        Disconnect a WebSocket client
        """
        self.logger.info(f"Disconnecting WebSocket for conversation {conversation_id} and websocket {websocket}")
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id] = [
                ws for ws in self.active_connections[conversation_id] if ws != websocket
            ]
            # Clean up if list becomes empty
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]

        self.logger.info(f"WebSocket disconnected from conversation {conversation_id}")
    
    async def send_personal_message(self, message: WebSocketMessage, websocket: WebSocket):
        """
        Send a message to a specific WebSocket
        """
        try:
            await websocket.send_text(message.to_json())
        except Exception as e:
            self.logger.error(f"Error sending WebSocket message: {str(e)}")
    
    async def broadcast(self, message: WebSocketMessage):
        """
        Broadcast a message to all connected clients for a conversation
        """
        self.logger.info(f"Broadcasting message: {message.to_json()}")
        conversation_id = message.conversation_id
        if conversation_id not in self.active_connections:
            self.logger.warning(f"No active connections for conversation {conversation_id}")
            return
        try:
            if conversation_id in self.active_connections:
                for websocket in self.active_connections[conversation_id]:
                    await websocket.send_text(message.to_json())
        except Exception as e:
            self.logger.error(f"Error broadcasting message: {str(e)}")

    async def broadcast_task_status(self, conversation_id: str, task_id: str, task_description: str, status: str, details: Dict[str, Any] = None):
        """
        Broadcast a task status update
        """
        await self.broadcast(
            WebSocketMessage(
                type="task_status",
                conversation_id=conversation_id,
                content={
                    "task_id": task_id,
                    "task_description": task_description,
                    "status": status,
                    "details": details or {}
                }
            )
        )
    
    async def broadcast_agent_thinking(self, conversation_id: str, is_thinking: bool = True):
        """
        Broadcast agent thinking status (for typing indicators)
        """
        await self.broadcast(
            WebSocketMessage(
                type="agent_thinking",
                conversation_id=conversation_id,
                content={"is_thinking": is_thinking}
            )
        )
    
    async def broadcast_plan_update(self, conversation_id: str, plan_id: str, tasks: List[Dict[str, Any]]):
        """
        Broadcast plan updates
        """
        await self.broadcast(
            WebSocketMessage(
                type="plan_update",
                conversation_id=conversation_id,
                content={
                    "plan_id": plan_id,
                    "task_count": len(tasks),
                    "tasks": tasks
                }
            )
        )
    
    async def broadcast_error(self, conversation_id: str, error_message: str, error_code: str = "error"):
        """
        Broadcast an error message
        """
        await self.broadcast(
            WebSocketMessage(
                type="error",
                conversation_id=conversation_id,
                content={
                    "error": error_message,
                    "code": error_code
                }
            )
        )

# Singleton instance
_connection_manager: Optional[ConnectionManager] = None

def get_connection_manager() -> ConnectionManager:
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager