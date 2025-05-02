# api/websockets/connection_manager.py
from fastapi import WebSocket
from typing import Dict, List, Any

# Import the WebSocketMessage model
from api.models.websocket_message import WebSocketMessage

from monitoring.agent_logger import get_logger

logger = get_logger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting
    """
    
    def __init__(self):
        # Map conversation_id -> list of connected websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, conversation_id: str):
        """
        Connect a new WebSocket client
        """
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.info(f"New WebSocket connection for conversation {conversation_id}")
        
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
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
            # Clean up empty conversation lists
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
        logger.info(f"WebSocket disconnected from conversation {conversation_id}")
    
    async def send_personal_message(self, message: WebSocketMessage, websocket: WebSocket):
        """
        Send a message to a specific WebSocket
        """
        try:
            await websocket.send_text(message.to_json())
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
    
    async def broadcast(self, message: WebSocketMessage):
        """
        Broadcast a message to all connected clients for a conversation
        """
        conversation_id = message.conversation_id
        if conversation_id not in self.active_connections:
            logger.warning(f"No active connections for conversation {conversation_id}")
            return
            
        disconnected_websockets = []
        
        for websocket in self.active_connections[conversation_id]:
            try:
                await websocket.send_text(message.to_json())
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")
                disconnected_websockets.append(websocket)
        
        # Clean up any disconnected websockets
        for websocket in disconnected_websockets:
            self.disconnect(websocket, conversation_id)
    
    async def broadcast_task_status(self, conversation_id: str, task_id: str, status: str, details: Dict[str, Any] = None):
        """
        Broadcast a task status update
        """
        await self.broadcast(
            WebSocketMessage(
                type="task_status",
                conversation_id=conversation_id,
                content={
                    "task_id": task_id,
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