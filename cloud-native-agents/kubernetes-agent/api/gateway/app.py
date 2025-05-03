# api/gateway/app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

# Import controllers
from api.controllers.conversation_controller import router as conversation_router
from api.controllers.tools_controller import router as tools_router
from api.websockets.connection_manager import get_connection_manager
from api.models.websocket_message import WebSocketMessage

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Kubernetes AI Agent API",
    description="API Gateway for interacting with the Kubernetes AI Agent",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create WebSocket connection manager
connection_manager = get_connection_manager()

# Include API routers
app.include_router(
    conversation_router,
    prefix="/api/conversations",
    tags=["conversations"]
)

app.include_router(
    tools_router,
    prefix="/api/tools",
    tags=["tools"]
)

def load_all_singleton_instances():
    """
    Load all singleton instances for the application.
    This function is called at startup to ensure all singletons are initialized.
    """
    from api.websockets.connection_manager import get_connection_manager
    from core.agent import get_kubernetes_agent
    from core.conversation_manager_api import get_conversation_manager_api
    from memory.long_term_memory import get_long_term_memory
    from memory.short_term_memory import get_short_term_memory
    from memory.memory_store import get_memory_store
    from monitoring.agent_logger import get_logger
    from monitoring.cost_tracker import get_cost_tracker
    from monitoring.metrics_collector import get_metrics_collector
    from monitoring.event_audit_log import get_audit_logger
    from planning.planner import get_planner
    from planning.task_decomposer import get_task_decomposer
    from planning.task_executor import get_task_executor
    from reflection.plan_improver import get_plan_improver
    from reflection.reflection_engine import get_reflection_engine
    from reflection.retry_policy import get_retry_policy
    from services.conversation.conversation_service import get_conversation_service
    from tools.registry import get_tools_registry

    get_connection_manager()
    get_kubernetes_agent()
    get_conversation_manager_api()
    get_long_term_memory()
    get_short_term_memory()
    get_memory_store()
    get_logger()
    get_cost_tracker()
    get_metrics_collector()
    get_audit_logger()
    get_planner()
    get_task_decomposer(config_path=None)
    get_task_executor(config_path=None)
    get_plan_improver()
    get_reflection_engine()
    get_retry_policy(max_retries=2)
    get_conversation_service()
    get_tools_registry()

    logger.info("All singleton instances loaded successfully.")


load_all_singleton_instances()

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "kubernetes-agent-api"}

@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time updates on conversations"""
    await connection_manager.connect(websocket, conversation_id)
    try:
        while True:
            # Wait for any message from the client
            data = await websocket.receive_text()
            
            # Process client message 
            try:
                message = json.loads(data)
                logger.info(f"Received WebSocket message for conversation {conversation_id}")
                
                # Echo back acknowledgment
                await connection_manager.send_personal_message(
                    WebSocketMessage(
                        type="acknowledgment",
                        conversation_id=conversation_id,
                        content={"received": True}
                    ),
                    websocket
                )
                
            except json.JSONDecodeError:
                logger.error(f"Invalid WebSocket message format: {data}")
                await connection_manager.send_personal_message(
                    WebSocketMessage(
                        type="error",
                        conversation_id=conversation_id,
                        content={"error": "Invalid message format"}
                    ),
                    websocket
                )
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, conversation_id)
        logger.info(f"Client disconnected from conversation {conversation_id}")

# Run with: uvicorn api.gateway.app:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)