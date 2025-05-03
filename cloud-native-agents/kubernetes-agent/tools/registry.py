from typing import List, Optional
from pydantic import BaseModel

from monitoring.agent_logger import get_logger

class Tool(BaseModel):
    """
    A base class for tools that can be used in the Kubernetes agent.
    """
    name: str
    description: str
    category: str


class ToolsRegistry:
    """
    A registry for tools that can be used in the Kubernetes agent.
    """

    def __init__(self):
        self.tools: List[Tool] = []
        self.logger = get_logger(__name__)

    def register_tool(self, tool: Tool):
        """
        Register a tool in the registry.
        :param tool: The tool to register.
        """
        if not isinstance(tool, Tool):
            raise ValueError("Tool must be an instance of Tool class.")
        if not any(t.name == tool.name for t in self.tools):
            self.tools.append(tool)
        else:
            self.logger.warning(f"Tool {tool.name} is already registered.")

    def list_tools(self):
        """
        List all registered tools.
        :return: A list of registered tools.
        """
        return self.tools
    
    def get_tool_by_category(self, category: str):
        """
        Get tools by category.
        :param category: The category of the tools to get.
        :return: A list of tools in the specified category.
        """
        return [tool for tool in self.tools if tool.category == category]
    
# Singleton instance
_tools_registry: Optional[ToolsRegistry] = None

def get_tools_registry() -> ToolsRegistry:
    global _tools_registry
    if _tools_registry is None:
        _tools_registry = ToolsRegistry()
    return _tools_registry