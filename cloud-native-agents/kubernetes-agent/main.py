# main.py
import uvicorn
import os
from fastapi.middleware.cors import CORSMiddleware

# Import API gateway
from api.gateway.app import app as api_app


from monitoring.agent_logger import get_logger

logger = get_logger(__name__)

# Add any additional configuration
origins = [
    "http://localhost",
    "http://localhost:3000",  # React frontend
    "http://localhost:8080",  # Vue frontend
    "null" # allow file:// access
]

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main entrypoint
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Kubernetes AI Agent API on {host}:{port}")
    
    uvicorn.run(
        "api.gateway.app:app", 
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )