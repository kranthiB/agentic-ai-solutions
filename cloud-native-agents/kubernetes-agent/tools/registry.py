# tools/registry.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class Tool(BaseModel):
    """
    Model representing a tool that can be used by the agent.
    """
    name: str
    description: str
    category: str
    permissions: Optional[List[str]] = None  # NEW: Tool permissions field
    risk_level: Optional[str] = None  # NEW: Tool risk level field
    protected: Optional[bool] = False  # NEW: Protected flag for sensitive tools

class ToolsRegistry:
    """
    Registry for all available tools that the agent can use.
    """
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        
    def register_tool(self, tool: Tool):
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool object to register
        """
        self.tools[tool.name] = tool
        
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Name of the tool to retrieve
            
        Returns:
            Tool object if found, None otherwise
        """
        return self.tools.get(name)
        
    def list_tools(self) -> List[Tool]:
        """
        List all registered tools.
        
        Returns:
            List of all registered Tool objects
        """
        return list(self.tools.values())
    
    def list_tools_by_category(self, category: str) -> List[Tool]:
        """
        List tools by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of Tool objects in the specified category
        """
        return [tool for tool in self.tools.values() if tool.category == category]
    
    # NEW: Guardrail-specific methods
    def check_permission(self, tool_name: str, user_role: str) -> bool:
        """
        Check if a user role has permission to use a tool
        
        Args:
            tool_name: Name of the tool to check
            user_role: User role (viewer, editor, admin)
            
        Returns:
            True if permitted, False otherwise
        """
        tool = self.get_tool(tool_name)
        
        # If tool doesn't exist, permission denied
        if not tool:
            return False
            
        # If tool has no permissions defined, default to admin-only
        if not tool.permissions:
            return user_role == "admin"
            
        # Check if user role is in the permitted roles
        return user_role in tool.permissions
    
    def get_tool_risk_level(self, tool_name: str) -> str:
        """
        Get the risk level of a tool
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            Risk level (low, medium, high) or "unknown" if not defined
        """
        tool = self.get_tool(tool_name)
        
        # If tool doesn't exist, return unknown
        if not tool:
            return "unknown"
            
        # Return the defined risk level or default to "medium"
        return tool.risk_level or "medium"
    
    def is_protected_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is protected (sensitive/critical)
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if protected, False otherwise
        """
        tool = self.get_tool(tool_name)
        
        # If tool doesn't exist, return False
        if not tool:
            return False
            
        # Return the protected flag
        return tool.protected or False
    
    def filter_tools_by_permission(self, user_role: str) -> List[Tool]:
        """
        Filter tools by user permission level
        
        Args:
            user_role: User role to filter by
            
        Returns:
            List of Tool objects permitted for the user role
        """
        return [
            tool for tool in self.tools.values() 
            if not tool.permissions or user_role in tool.permissions
        ]

# Singleton instance
_tools_registry: Optional[ToolsRegistry] = None

def get_tools_registry() -> ToolsRegistry:
    """
    Get the singleton instance of the tools registry.
    
    Returns:
        ToolsRegistry instance
    """
    global _tools_registry
    if _tools_registry is None:
        _tools_registry = ToolsRegistry()
    return _tools_registry