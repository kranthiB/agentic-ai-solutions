# api/gateway/app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

# Import controllers
from api.controllers.conversation_controller import router as conversation_router
from api.websockets.connection_manager import ConnectionManager
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
connection_manager = ConnectionManager()

# Include API routers
app.include_router(
    conversation_router,
    prefix="/api/conversations",
    tags=["conversations"]
)

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