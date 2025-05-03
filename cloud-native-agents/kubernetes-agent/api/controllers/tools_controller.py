from fastapi import APIRouter, status
from monitoring.agent_logger import get_logger
from api.models.tool import ToolsResponse

from tools.registry import get_tools_registry
logger = get_logger(__name__)

# Initialize router
router = APIRouter()
tools_registry = get_tools_registry()

@router.get("/", response_model=ToolsResponse, status_code=status.HTTP_200_OK)
async def list_tools():
    """
    List all registered tools.
    :return: A list of registered tools.
    """
    return ToolsResponse(tools=tools_registry.list_tools())