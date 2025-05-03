# services/guardrail/guardrail_service.py
import yaml
import re
from typing import Dict, List, Tuple, Optional, Any
import asyncio

# Import validators
from services.guardrail.validators.input_validator import InputValidator
from services.guardrail.validators.action_validator import ActionValidator
from services.guardrail.validators.output_validator import OutputValidator

# Import monitoring
from monitoring.agent_logger import get_logger
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger

class GuardrailService:
    """
    Central service for implementing AI agent guardrails.
    
    This service coordinates various validation components to ensure that:
    1. User inputs are safe and appropriate
    2. Agent actions are permitted and safe
    3. LLM outputs are filtered for harmful content
    4. Risk assessments are performed for critical operations
    """
    
    def __init__(self, config_path: str = "configs/guardrail_config.yaml"):
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize validators
        self.input_validator = InputValidator(self.config.get("input_validation", {}))
        self.action_validator = ActionValidator(self.config.get("action_validation", {}))
        self.output_validator = OutputValidator(self.config.get("output_validation", {}))
        
        # Initialize guardrail metrics
        self.metrics.record_tool_call("guardrail_service_initialized")
        self.logger.info("GuardrailService initialized with config from: %s", config_path)
        
        # Cache for operation permissions
        self._permission_cache = {}
        
    def _load_config(self, path: str) -> Dict:
        """Load guardrail configuration from YAML"""
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
                return config.get("guardrails", {})
        except FileNotFoundError:
            self.logger.warning(f"Guardrail config file {path} not found. Using default configuration.")
            return {
                "enabled": True,
                "enforcement_level": "warning",  # warning, block, passive
                "input_validation": {"enabled": True},
                "action_validation": {"enabled": True},
                "output_validation": {"enabled": True}
            }
    
    async def validate_user_input(self, 
                                 user_input: str, 
                                 user_id: str = "anonymous",
                                 conversation_id: str = None,
                                 metadata: Dict = None) -> Tuple[bool, str]:
        """
        Validate user input for safety and policy compliance
        
        Args:
            user_input: The raw user input to validate
            user_id: User identifier
            conversation_id: Optional conversation context
            metadata: Additional metadata for validation context
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not self.config.get("enabled", True) or not self.config.get("input_validation", {}).get("enabled", True):
            return True, ""
            
        validation_start = asyncio.get_event_loop().time()
        
        # Record validation attempt
        self.metrics.record_tool_call("input_validation_attempt")
        
        # Get validation result
        is_valid, reason = await self.input_validator.validate(
            user_input, 
            user_id=user_id,
            conversation_id=conversation_id,
            metadata=metadata or {}
        )
        
        # Record timing and result
        validation_end = asyncio.get_event_loop().time()
        self.metrics.record_task_duration(
            "input_validation", 
            validation_start, 
            validation_end
        )
        
        # Record validation result
        self.metrics.record_tool_result("input_validation", is_valid)
        
        # Log the validation result
        if not is_valid:
            self.logger.warning(f"Input validation failed: {reason}")
            self.audit.log_event("guardrail_input_blocked", {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "reason": reason,
                # Don't log the full input for privacy, just a sanitized fragment
                "input_fragment": self._sanitize_fragment(user_input)
            })
        
        return is_valid, reason
    
    async def validate_action(self, 
                             action: str, 
                             parameters: Dict, 
                             user_id: str = "anonymous",
                             user_role: str = "viewer",
                             namespace: str = "default") -> Tuple[bool, str]:
        """
        Validate if a Kubernetes action is permitted and safe
        
        Args:
            action: The tool or action name to validate
            parameters: Action parameters
            user_id: User identifier
            user_role: User's role (viewer, editor, admin)
            namespace: Kubernetes namespace
            
        Returns:
            Tuple of (is_permitted, reason_if_denied)
        """
        if not self.config.get("enabled", True) or not self.config.get("action_validation", {}).get("enabled", True):
            return True, ""
            
        validation_start = asyncio.get_event_loop().time()
        
        # Record validation attempt
        self.metrics.record_tool_call("action_validation_attempt")
        
        # Get validation result
        is_valid, reason = await self.action_validator.validate(
            action=action,
            parameters=parameters,
            user_id=user_id,
            user_role=user_role,
            namespace=namespace
        )
        
        # Record timing and result
        validation_end = asyncio.get_event_loop().time()
        self.metrics.record_task_duration(
            "action_validation", 
            validation_start, 
            validation_end
        )
        
        # Record validation result
        self.metrics.record_tool_result("action_validation", is_valid)
        
        # Log the validation result
        if not is_valid:
            self.logger.warning(f"Action validation failed: {reason}")
            self.audit.log_event("guardrail_action_blocked", {
                "user_id": user_id,
                "user_role": user_role,
                "action": action,
                "namespace": namespace,
                "reason": reason,
                "parameters": {k: str(v)[:50] for k, v in parameters.items()}  # Truncate large values
            })
        
        return is_valid, reason
        
    async def validate_llm_output(self, 
                                 output: str, 
                                 context: Dict = None) -> Tuple[bool, str, str]:
        """
        Validate LLM output for safety, harmful content, etc.
        
        Args:
            output: Raw LLM output to validate
            context: Additional context about the generation
            
        Returns:
            Tuple of (is_safe, reason_if_unsafe, filtered_output)
        """
        if not self.config.get("enabled", True) or not self.config.get("output_validation", {}).get("enabled", True):
            return True, "", output
            
        validation_start = asyncio.get_event_loop().time()
        
        # Record validation attempt
        self.metrics.record_tool_call("output_validation_attempt")
        
        # Get validation result
        is_valid, reason, filtered_output = await self.output_validator.validate(
            output, 
            context=context or {}
        )
        
        # Record timing and result
        validation_end = asyncio.get_event_loop().time()
        self.metrics.record_task_duration(
            "output_validation", 
            validation_start, 
            validation_end
        )
        
        # Record validation result
        self.metrics.record_tool_result("output_validation", is_valid)
        
        # Log the validation result
        if not is_valid:
            self.logger.warning(f"Output validation modified content: {reason}")
            self.audit.log_event("guardrail_output_filtered", {
                "reason": reason,
                "modified": output != filtered_output
            })
        
        return is_valid, reason, filtered_output
    
    async def analyze_operation_risk(self, 
                                    operation: str, 
                                    resource_type: str,
                                    namespace: str = "default") -> Dict:
        """
        Analyze risk level of a Kubernetes operation
        
        Args:
            operation: Operation type (e.g., delete, scale, etc.)
            resource_type: Resource type (pod, deployment, etc.)
            namespace: Kubernetes namespace
            
        Returns:
            Dict with risk assessment details
        """
        # Get operation risk profile
        risk_levels = self.config.get("risk_profiles", {}).get(operation, {})
        resource_risk = risk_levels.get(resource_type, "medium")
        
        # Check namespace criticality
        critical_namespaces = self.config.get("critical_namespaces", ["kube-system", "monitoring"])
        is_critical_namespace = namespace in critical_namespaces
        
        # Determine final risk level
        if is_critical_namespace:
            risk_level = "high"  # Operations in critical namespaces are always high risk
        else:
            risk_level = resource_risk
            
        # Create detailed assessment
        assessment = {
            "operation": operation,
            "resource_type": resource_type,
            "namespace": namespace,
            "risk_level": risk_level,
            "requires_approval": risk_level == "high",
            "is_critical_namespace": is_critical_namespace,
            "mitigation_steps": self._get_mitigation_steps(operation, resource_type, risk_level)
        }
        
        # Log risk assessment
        if risk_level == "high":
            self.logger.warning(f"High-risk operation detected: {operation} on {resource_type} in {namespace}")
            self.audit.log_event("high_risk_operation_flagged", assessment)
            
        return assessment
    
    def _get_mitigation_steps(self, operation: str, resource_type: str, risk_level: str) -> List[str]:
        """Get recommended mitigation steps based on operation and risk level"""
        mitigations = []
        
        if operation == "delete":
            mitigations.append("Consider backing up the resource before deletion")
            
        if risk_level == "high":
            mitigations.append("Obtain approval from a cluster administrator")
            mitigations.append("Perform in a maintenance window if possible")
            
        if resource_type in ["deployment", "statefulset"]:
            mitigations.append("Ensure enough replica count to maintain availability")
            
        return mitigations
    
    def check_permission(self, user_role: str, operation: str, resource_type: str) -> bool:
        """
        Check if a user role has permission for an operation
        
        Args:
            user_role: User role (viewer, editor, admin)
            operation: Operation type (get, list, create, delete, etc.)
            resource_type: Resource type (pod, deployment, etc.)
            
        Returns:
            True if allowed, False if denied
        """
        # Check cache first for performance
        cache_key = f"{user_role}:{operation}:{resource_type}"
        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]
            
        # Get role permissions
        role_permissions = self.config.get("role_permissions", {}).get(user_role, {})
        
        # Check global operations for the role
        allowed_operations = role_permissions.get("global_operations", [])
        
        # Check resource-specific permissions
        resource_permissions = role_permissions.get("resources", {}).get(resource_type, [])
        allowed_operations.extend(resource_permissions)
        
        # Determine if operation is allowed
        is_allowed = operation in allowed_operations
        
        # Cache the result
        self._permission_cache[cache_key] = is_allowed
        
        return is_allowed
    
    def _sanitize_fragment(self, text: str, max_length: int = 30) -> str:
        """Create a safe fragment of text for logging (no PII or sensitive info)"""
        if not text:
            return ""
            
        # Truncate
        fragment = text[:max_length] + ("..." if len(text) > max_length else "")
        
        # Remove potential PII patterns
        fragment = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', fragment)
        fragment = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', fragment)
        
        return fragment

# Singleton instance
_guardrail_service: Optional[GuardrailService] = None

def get_guardrail_service() -> GuardrailService:
    """Get singleton instance of GuardrailService"""
    global _guardrail_service
    if _guardrail_service is None:
        _guardrail_service = GuardrailService()
    return _guardrail_service