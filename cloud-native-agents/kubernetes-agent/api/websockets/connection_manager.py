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
        # Map conversation_id -> session state
        self.session_states: Dict[str, Dict[str, Any]] = {}
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
        
        # Initialize session state if needed
        if conversation_id not in self.session_states:
            self.session_states[conversation_id] = {
                "status": "connected",
                "connection_time": self._get_current_timestamp()
            }
        
        # Send initial connection confirmation with current state
        await self.send_personal_message(
            WebSocketMessage(
                type="connection_established",
                conversation_id=conversation_id,
                content={
                    "status": "connected",
                    "state": self.session_states[conversation_id]
                }
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
                # Optionally, preserve session state even after all connections are closed
                # del self.session_states[conversation_id]

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
        # Update session state first
        if conversation_id in self.session_states:
            if "tasks" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["tasks"] = {}
            
            self.session_states[conversation_id]["tasks"][task_id] = {
                "description": task_description,
                "status": status,
                "updated_at": self._get_current_timestamp(),
                **(details or {})
            }
        
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
        # Update session state
        if conversation_id in self.session_states:
            self.session_states[conversation_id]["agent_thinking"] = is_thinking
            self.session_states[conversation_id]["last_thinking_update"] = self._get_current_timestamp()
        
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
        # Update session state
        if conversation_id in self.session_states:
            self.session_states[conversation_id]["plan"] = {
                "plan_id": plan_id,
                "task_count": len(tasks),
                "tasks": tasks,
                "created_at": self._get_current_timestamp()
            }
        
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
        # Update session state
        if conversation_id in self.session_states:
            if "errors" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["errors"] = []
            
            self.session_states[conversation_id]["errors"].append({
                "message": error_message,
                "code": error_code,
                "timestamp": self._get_current_timestamp()
            })
        
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
        
    # NEW: Guardrail-specific WebSocket broadcasts
    async def broadcast_guardrail_warning(self, 
                                        conversation_id: str, 
                                        warning_type: str, 
                                        message: str, 
                                        details: Dict[str, Any] = None):
        """
        Broadcast a guardrail warning message
        
        Args:
            conversation_id: ID of the conversation
            warning_type: Type of warning (input, action, output)
            message: Warning message text
            details: Additional warning details
        """
        # Update session state
        if conversation_id in self.session_states:
            if "guardrail_warnings" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["guardrail_warnings"] = []
            
            self.session_states[conversation_id]["guardrail_warnings"].append({
                "warning_type": warning_type,
                "message": message,
                "details": details or {},
                "timestamp": self._get_current_timestamp()
            })
        
        await self.broadcast(
            WebSocketMessage(
                type="guardrail_warning",
                conversation_id=conversation_id,
                content={
                    "warning_type": warning_type,
                    "message": message,
                    "details": details or {}
                }
            )
        )
        
    async def broadcast_guardrail_block(self, 
                                      conversation_id: str, 
                                      block_type: str, 
                                      reason: str, 
                                      details: Dict[str, Any] = None):
        """
        Broadcast a guardrail block notification
        
        Args:
            conversation_id: ID of the conversation
            block_type: Type of block (input, action, output)
            reason: Reason for the block
            details: Additional block details
        """
        # Update session state
        if conversation_id in self.session_states:
            if "guardrail_blocks" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["guardrail_blocks"] = []
            
            self.session_states[conversation_id]["guardrail_blocks"].append({
                "block_type": block_type,
                "reason": reason,
                "details": details or {},
                "timestamp": self._get_current_timestamp()
            })
        
        await self.broadcast(
            WebSocketMessage(
                type="guardrail_block",
                conversation_id=conversation_id,
                content={
                    "block_type": block_type,
                    "reason": reason,
                    "details": details or {}
                }
            )
        )
        
    async def broadcast_risk_assessment(self, 
                                      conversation_id: str, 
                                      operation: str, 
                                      resource_type: str, 
                                      namespace: str,
                                      risk_level: str,
                                      requires_approval: bool = False,
                                      mitigation_steps: List[str] = None):
        """
        Broadcast a risk assessment notification
        
        Args:
            conversation_id: ID of the conversation
            operation: Operation being assessed (e.g., delete, scale)
            resource_type: Resource type (e.g., pod, deployment)
            namespace: Kubernetes namespace
            risk_level: Assessed risk level (low, medium, high)
            requires_approval: Whether explicit approval is required
            mitigation_steps: Recommended mitigation steps
        """
        # Update session state
        if conversation_id in self.session_states:
            if "risk_assessments" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["risk_assessments"] = []
            
            self.session_states[conversation_id]["risk_assessments"].append({
                "operation": operation,
                "resource_type": resource_type,
                "namespace": namespace,
                "risk_level": risk_level,
                "requires_approval": requires_approval,
                "mitigation_steps": mitigation_steps or [],
                "timestamp": self._get_current_timestamp()
            })
        
        await self.broadcast(
            WebSocketMessage(
                type="risk_assessment",
                conversation_id=conversation_id,
                content={
                    "operation": operation,
                    "resource_type": resource_type,
                    "namespace": namespace,
                    "risk_level": risk_level,
                    "requires_approval": requires_approval,
                    "mitigation_steps": mitigation_steps or []
                }
            )
        )
        
    async def broadcast_approval_request(self, 
                                       conversation_id: str, 
                                       operation: str, 
                                       resource_type: str,
                                       resource_name: str,
                                       namespace: str,
                                       risk_level: str,
                                       request_id: str,
                                       explanation: str = None):
        """
        Broadcast an approval request for a high-risk operation
        
        Args:
            conversation_id: ID of the conversation
            operation: Operation requiring approval (e.g., delete)
            resource_type: Resource type (e.g., node)
            resource_name: Name of the specific resource
            namespace: Kubernetes namespace
            risk_level: Risk level (typically "high")
            request_id: Unique ID for the approval request
            explanation: Optional explanation of risks
        """
        # Update session state
        if conversation_id in self.session_states:
            if "approval_requests" not in self.session_states[conversation_id]:
                self.session_states[conversation_id]["approval_requests"] = {}
            
            self.session_states[conversation_id]["approval_requests"][request_id] = {
                "operation": operation,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "namespace": namespace,
                "risk_level": risk_level,
                "explanation": explanation or f"High-risk operation '{operation}' on {resource_type}/{resource_name} requires approval",
                "status": "pending",
                "timestamp": self._get_current_timestamp()
            }
        
        await self.broadcast(
            WebSocketMessage(
                type="approval_request",
                conversation_id=conversation_id,
                content={
                    "request_id": request_id,
                    "operation": operation,
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "risk_level": risk_level,
                    "explanation": explanation or f"High-risk operation '{operation}' on {resource_type}/{resource_name} requires approval"
                }
            )
        )
    
    # New methods for enhanced session state management
    async def update_session_state(self, conversation_id: str, state_update: Dict[str, Any]):
        """
        Update the session state for a conversation
        
        Args:
            conversation_id: ID of the conversation
            state_update: Dictionary of state updates to apply
        """
        if conversation_id not in self.session_states:
            self.session_states[conversation_id] = {}
        
        # Update the state
        self.session_states[conversation_id].update(state_update)
        
        # Broadcast the state update
        await self.broadcast(
            WebSocketMessage(
                type="session_state_update",
                conversation_id=conversation_id,
                content={"state": state_update}
            )
        )
        
    def get_session_state(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get the current session state for a conversation
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            The current session state dictionary
        """
        return self.session_states.get(conversation_id, {})
    
    async def broadcast_progress_update(self, conversation_id: str, 
                                     progress_type: str, 
                                     percentage: float,
                                     current_step: int = None,
                                     total_steps: int = None,
                                     step_description: str = None):
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
        # Update session state first
        state_update = {
            f"{progress_type}_progress": {
                "percentage": percentage,
                "current_step": current_step,
                "total_steps": total_steps,
                "step_description": step_description,
                "updated_at": self._get_current_timestamp()
            }
        }
        if conversation_id in self.session_states:
            self.session_states[conversation_id].update(state_update)
        
        # Then broadcast detailed progress update
        await self.broadcast(
            WebSocketMessage(
                type="progress_update",
                conversation_id=conversation_id,
                content={
                    "progress_type": progress_type,
                    "percentage": percentage,
                    "current_step": current_step,
                    "total_steps": total_steps,
                    "step_description": step_description
                }
            )
        )
    
    async def broadcast_conversation_summary_update(self, conversation_id: str, summary: str):
        """
        Broadcast an updated conversation summary
        
        Args:
            conversation_id: ID of the conversation
            summary: Current conversation summary
        """
        # Update session state
        if conversation_id in self.session_states:
            self.session_states[conversation_id]["conversation_summary"] = {
                "text": summary,
                "updated_at": self._get_current_timestamp()
            }
        
        # Broadcast the update
        await self.broadcast(
            WebSocketMessage(
                type="conversation_summary",
                conversation_id=conversation_id,
                content={"summary": summary}
            )
        )
    
    async def broadcast_conversation_context(self, conversation_id: str, context_items: List[Dict[str, Any]]):
        """
        Broadcast current conversation context items to clients
        
        Args:
            conversation_id: ID of the conversation
            context_items: List of context items with their metadata
        """
        # Update session state
        if conversation_id in self.session_states:
            self.session_states[conversation_id]["context_items"] = {
                "items": context_items,
                "updated_at": self._get_current_timestamp()
            }
        
        # Broadcast the context
        await self.broadcast(
            WebSocketMessage(
                type="conversation_context",
                conversation_id=conversation_id,
                content={"context_items": context_items}
            )
        )
    
    def _get_current_timestamp(self) -> str:
        """Get the current timestamp in ISO format"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

# Singleton instance
_connection_manager: Optional[ConnectionManager] = None

def get_connection_manager() -> ConnectionManager:
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager