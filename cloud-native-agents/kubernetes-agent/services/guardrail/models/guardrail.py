# services/guardrail/models/guardrail.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum

class EnforcementLevel(str, Enum):
    """Enforcement level for guardrails"""
    PASSIVE = "passive"    # Log only, no enforcement
    WARNING = "warning"    # Warn the user but allow the operation
    BLOCK = "block"        # Block the operation
    
class ValidationResult(BaseModel):
    """Result of a guardrail validation"""
    valid: bool = Field(..., description="Whether the validation passed")
    reason: Optional[str] = Field(None, description="Reason for failure if failed")
    modified_content: Optional[str] = Field(None, description="Modified content if content was filtered")
    
class RiskLevel(str, Enum):
    """Risk level for operations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class RiskAssessment(BaseModel):
    """Risk assessment for an operation"""
    operation: str = Field(..., description="Operation being assessed")
    resource_type: str = Field(..., description="Resource type being operated on")
    namespace: str = Field(..., description="Kubernetes namespace")
    risk_level: RiskLevel = Field(..., description="Assessed risk level")
    requires_approval: bool = Field(..., description="Whether operation requires explicit approval")
    is_critical_namespace: bool = Field(..., description="Whether namespace is critical")
    mitigation_steps: List[str] = Field(default_factory=list, description="Recommended risk mitigation steps")

class GuardrailConfig(BaseModel):
    """Guardrail configuration model"""
    enabled: bool = Field(True, description="Whether guardrails are enabled")
    enforcement_level: EnforcementLevel = Field(EnforcementLevel.WARNING, description="Default enforcement level")
    
    input_validation: Dict[str, Any] = Field(default_factory=dict, description="Input validation configuration")
    action_validation: Dict[str, Any] = Field(default_factory=dict, description="Action validation configuration")
    output_validation: Dict[str, Any] = Field(default_factory=dict, description="Output validation configuration")
    
    role_permissions: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=dict, 
        description="Permissions for different user roles"
    )
    
    protected_resources: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Protected resources that require special permissions"
    )
    
    critical_namespaces: List[str] = Field(
        default_factory=list,
        description="Critical namespaces that require special handling"
    )
    
    risk_profiles: Dict[str, Dict[str, RiskLevel]] = Field(
        default_factory=dict,
        description="Risk profiles for different operations and resource types"
    )
    
    filter_patterns: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Patterns for filtering content"
    )
    
    class Config:
        """Pydantic config"""
        use_enum_values = True