# services/guardrail/validators/action_validator.py
from typing import Dict, Tuple
import re

from monitoring.agent_logger import get_logger

class ActionValidator:
    """
    Validates Kubernetes actions for permission, safety, and policy compliance.
    
    This validator checks:
    1. User permission for operations based on their role
    2. Resource safety (prevents dangerous operations)
    3. Resource impact and risk assessment
    """
    
    def __init__(self, config: Dict = None):
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Default role permissions if not specified in config
        self.role_permissions = self.config.get("role_permissions", {
            "viewer": ["get", "list", "describe", "watch"],
            "editor": ["get", "list", "describe", "watch", "create", "update", "patch", "apply"],
            "admin": ["get", "list", "describe", "watch", "create", "update", "patch", "apply", "delete", "exec"]
        })
        
        # Load protected resources
        self.protected_resources = self.config.get("protected_resources", {
            "namespaces": ["kube-system", "kube-public", "kube-node-lease", "monitoring"],
            "resource_types": ["nodes", "serviceaccounts", "secrets", "persistentvolumes"]
        })
        
        # Load critical resource patterns
        self.critical_resource_patterns = self.config.get("critical_resource_patterns", [
            r'(?i)^kube-',      # kube- prefixed resources
            r'(?i).*-system$',  # system suffixed resources
            r'(?i)^ingress-',   # ingress controllers
            r'(?i)^cert-',      # cert-manager resources
            r'(?i)^prometheus-' # Prometheus resources
        ])
        
        # High-risk operations and their resource types
        self.high_risk_operations = self.config.get("high_risk_operations", {
            "delete": ["nodes", "namespaces", "persistentvolumes", "clusterroles"],
            "patch": ["nodes", "customresourcedefinitions", "apiservices"],
            "exec": ["pods"],
            "drain": ["nodes"],
            "cordon": ["nodes"],
            "taint": ["nodes"]
        })
        
        self.logger.info("ActionValidator initialized")
    
    async def validate(self, 
                      action: str, 
                      parameters: Dict, 
                      user_id: str = "anonymous",
                      user_role: str = "viewer", 
                      namespace: str = "default") -> Tuple[bool, str]:
        """
        Validate a Kubernetes action
        
        Args:
            action: The tool or action name to validate
            parameters: Action parameters
            user_id: User identifier
            user_role: User's role (viewer, editor, admin)
            namespace: Kubernetes namespace
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Extract operation and resource type from action
        operation, resource_type = self._parse_action(action)
        
        # Check user role permissions
        if not self._check_role_permission(user_role, operation):
            return False, f"User role '{user_role}' does not have permission for operation '{operation}'"
        
        # Check protected namespace
        if namespace in self.protected_resources["namespaces"] and user_role != "admin":
            return False, f"Namespace '{namespace}' is protected and requires admin privileges"
        
        # Check protected resource types
        if resource_type in self.protected_resources["resource_types"] and user_role != "admin":
            return False, f"Resource type '{resource_type}' is protected and requires admin privileges"
        
        # Check resource name against critical patterns
        resource_name = parameters.get("name", "") or parameters.get("resource_name", "")
        if resource_name and self._is_critical_resource(resource_name) and user_role != "admin":
            return False, f"Resource '{resource_name}' appears to be critical and requires admin privileges"
        
        # Check high-risk operations
        if operation in self.high_risk_operations and resource_type in self.high_risk_operations[operation]:
            # For high-risk operations, require explicit confirmation
            if not parameters.get("confirmed", False):
                return False, f"High-risk operation '{operation}' on '{resource_type}' requires explicit confirmation"
        
        # All checks passed
        return True, ""
    
    def _parse_action(self, action: str) -> Tuple[str, str]:
        """
        Parse action string into operation and resource type
        
        Examples:
            - get_pod -> (get, pod)
            - list_deployments -> (list, deployments)
            - delete_namespace -> (delete, namespace)
        """
        # Handle special case mapping
        special_cases = {
            "exec_command_in_pod": ("exec", "pod"),
            "kubectl_get": ("get", "resource"),
            "kubectl_describe": ("describe", "resource"),
            "kubectl_delete": ("delete", "resource"),
            "kubectl_apply": ("apply", "resource"),
            "kubectl_patch": ("patch", "resource"),
        }
        
        if action in special_cases:
            return special_cases[action]
        
        # Standard parsing for <operation>_<resource> format
        parts = action.split('_', 1)
        if len(parts) == 2:
            operation, resource = parts
            # Handle plural resources (list_pods -> list, pod)
            if resource.endswith('s') and operation == "list":
                resource = resource[:-1]
            return operation, resource
        
        # Default fallback if we can't parse
        return action, "unknown"
    
    def _check_role_permission(self, user_role: str, operation: str) -> bool:
        """Check if user role has permission for the operation"""
        allowed_operations = self.role_permissions.get(user_role, [])
        return operation in allowed_operations
    
    def _is_critical_resource(self, resource_name: str) -> bool:
        """Check if a resource name matches critical patterns"""
        for pattern in self.critical_resource_patterns:
            if re.search(pattern, resource_name):
                return True
        return False