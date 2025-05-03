from pydantic import BaseModel
from tools.registry import Tool


class ToolsResponse(BaseModel):
    """
    Response model for tools.
    """
    tools: list[Tool] = []