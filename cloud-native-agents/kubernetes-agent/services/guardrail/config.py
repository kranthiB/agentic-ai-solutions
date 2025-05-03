# services/guardrail/config.py
import os
import yaml
from typing import Dict, Any, Optional
from services.guardrail.models.guardrail import GuardrailConfig, EnforcementLevel, RiskLevel

class GuardrailConfigManager:
    """
    Manages guardrail configuration including loading, validation, and access.
    
    This manager handles:
    1. Loading configuration from YAML
    2. Environment-specific overrides
    3. Dynamic configuration updates
    4. Configuration validation
    """
    
    def __init__(self, config_path: str = "configs/guardrail_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
        
    def _load_config(self) -> GuardrailConfig:
        """Load configuration from YAML file with environment overrides"""
        try:
            # Check if file exists
            if not os.path.exists(self.config_path):
                return self._get_default_config()
                
            # Load from file
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)
                
            # Get guardrails section
            guardrail_data = config_data.get("guardrails", {})
            
            # Apply environment overrides
            self._apply_env_overrides(guardrail_data)
            
            # Create model instance
            return GuardrailConfig(**guardrail_data)
            
        except Exception as e:
            print(f"Error loading guardrail config: {str(e)}")
            return self._get_default_config()
            
    def _get_default_config(self) -> GuardrailConfig:
        """Get default configuration"""
        return GuardrailConfig(
            enabled=True,
            enforcement_level=EnforcementLevel.WARNING,
            input_validation={"enabled": True},
            action_validation={"enabled": True},
            output_validation={"enabled": True},
            role_permissions={
                "viewer": {
                    "global_operations": ["get", "list", "describe", "watch"],
                    "resources": {}
                },
                "editor": {
                    "global_operations": ["get", "list", "describe", "watch", "create", "update", "patch", "apply"],
                    "resources": {}
                },
                "admin": {
                    "global_operations": ["get", "list", "describe", "watch", "create", "update", "patch", "apply", "delete", "exec"],
                    "resources": {
                        "nodes": ["cordon", "uncordon", "drain", "taint"]
                    }
                }
            },
            protected_resources={
                "namespaces": ["kube-system", "kube-public", "kube-node-lease", "monitoring"],
                "resource_types": ["nodes", "serviceaccounts", "secrets", "persistentvolumes"]
            },
            critical_namespaces=["kube-system", "monitoring"],
            risk_profiles={
                "delete": {
                    "pods": RiskLevel.MEDIUM,
                    "deployments": RiskLevel.MEDIUM,
                    "nodes": RiskLevel.HIGH,
                    "namespaces": RiskLevel.HIGH,
                    "persistentvolumes": RiskLevel.HIGH
                },
                "exec": {
                    "pods": RiskLevel.MEDIUM
                },
                "drain": {
                    "nodes": RiskLevel.HIGH
                }
            }
        )
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> None:
        """Apply environment variable overrides to configuration"""
        # Check for enabled override
        if os.environ.get("GUARDRAIL_ENABLED") is not None:
            config_data["enabled"] = os.environ.get("GUARDRAIL_ENABLED").lower() == "true"
            
        # Check for enforcement level override
        if os.environ.get("GUARDRAIL_ENFORCEMENT_LEVEL") is not None:
            level = os.environ.get("GUARDRAIL_ENFORCEMENT_LEVEL").lower()
            if level in ["passive", "warning", "block"]:
                config_data["enforcement_level"] = level
    
    def _validate_config(self) -> None:
        """Validate configuration for consistency"""
        # Perform validation logic here
        pass
    
    def get_config(self) -> GuardrailConfig:
        """Get the current configuration"""
        return self.config
        
    def reload_config(self) -> GuardrailConfig:
        """Reload configuration from file"""
        self.config = self._load_config()
        self._validate_config()
        return self.config

# Singleton instance
_config_manager: Optional[GuardrailConfigManager] = None

def get_guardrail_config() -> GuardrailConfig:
    """Get singleton instance of guardrail configuration"""
    global _config_manager
    if _config_manager is None:
        _config_manager = GuardrailConfigManager()
    return _config_manager.get_config()