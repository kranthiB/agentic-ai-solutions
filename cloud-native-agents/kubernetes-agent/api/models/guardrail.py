# api/models/guardrail.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum


class EnforcementLevel(str, Enum):
    """Enforcement level for guardrails"""
    PASSIVE = "passive"    # Log only, no enforcement
    WARNING = "warning"    # Warn the user but allow the operation
    BLOCK = "block"        # Block the operation


class RiskLevel(str, Enum):
    """Risk level for operations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ValidationRequest(BaseModel):
    """Request to validate user input or action"""
    content: str = Field(..., description="Content to validate")
    user_id: Optional[str] = Field(None, description="User ID")
    user_role: Optional[str] = Field("viewer", description="User role")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    namespace: Optional[str] = Field("default", description="Kubernetes namespace")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ValidationResponse(BaseModel):
    """Response from validation API"""
    valid: bool = Field(..., description="Whether validation passed")
    reason: Optional[str] = Field(None, description="Reason for failure if not valid")
    modified_content: Optional[str] = Field(None, description="Modified content if changed")
    risk_level: Optional[str] = Field(None, description="Risk level assessment")
    enforcement: str = Field(..., description="Enforcement action taken")


class ActionValidationRequest(BaseModel):
    """Request to validate a Kubernetes action"""
    action: str = Field(..., description="Action name to validate")
    parameters: Dict[str, Any] = Field(..., description="Action parameters")
    user_id: Optional[str] = Field(None, description="User ID")
    user_role: str = Field("viewer", description="User role")
    namespace: str = Field("default", description="Kubernetes namespace")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class GuardrailStatusResponse(BaseModel):
    """Response with guardrail status information"""
    enabled: bool = Field(..., description="Whether guardrails are enabled")
    enforcement_level: str = Field(..., description="Current enforcement level")
    input_validation: bool = Field(..., description="Input validation status")
    action_validation: bool = Field(..., description="Action validation status") 
    output_validation: bool = Field(..., description="Output validation status")


class GuardrailConfigUpdateRequest(BaseModel):
    """Request to update guardrail configuration"""
    enabled: Optional[bool] = Field(None, description="Whether guardrails are enabled")
    enforcement_level: Optional[str] = Field(None, description="Enforcement level")
    input_validation: Optional[bool] = Field(None, description="Enable input validation")
    action_validation: Optional[bool] = Field(None, description="Enable action validation")
    output_validation: Optional[bool] = Field(None, description="Enable output validation")