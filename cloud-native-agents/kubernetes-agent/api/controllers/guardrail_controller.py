# api/controllers/guardrail_controller.py
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Optional

# Import models
from api.models.guardrail import (
    ValidationRequest,
    ValidationResponse,
    ActionValidationRequest,
    GuardrailStatusResponse,
    GuardrailConfigUpdateRequest
)

# Import services
from services.guardrail.guardrail_service import get_guardrail_service
from services.guardrail.config import get_guardrail_config

# Import monitoring
from monitoring.agent_logger import get_logger
from monitoring.guardrail_metrics import record_guardrail_api_call

# Initialize router
router = APIRouter()
logger = get_logger(__name__)


@router.get("/status", response_model=GuardrailStatusResponse)
async def get_guardrail_status():
    """
    Get current status of guardrail system
    """
    record_guardrail_api_call("get_status")
    
    try:
        # Get guardrail config
        config = get_guardrail_config()
        
        return GuardrailStatusResponse(
            enabled=config.enabled,
            enforcement_level=config.enforcement_level,
            input_validation=config.input_validation.get("enabled", True),
            action_validation=config.action_validation.get("enabled", True),
            output_validation=config.output_validation.get("enabled", True)
        )
    except Exception as e:
        logger.error(f"Error retrieving guardrail status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving guardrail status: {str(e)}"
        )


@router.post("/validate/input", response_model=ValidationResponse)
async def validate_input(request: ValidationRequest):
    """
    Validate user input for safety and policy compliance
    """
    record_guardrail_api_call("validate_input")
    
    try:
        # Get guardrail service
        guardrail_service = get_guardrail_service()
        
        # Perform validation
        is_valid, reason = await guardrail_service.validate_user_input(
            user_input=request.content,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            metadata=request.metadata
        )
        
        # Get config for enforcement level
        config = get_guardrail_config()
        enforcement = config.enforcement_level
        
        return ValidationResponse(
            valid=is_valid,
            reason=reason if not is_valid else None,
            modified_content=None,  # Input validation doesn't modify content
            risk_level=None,  # Input validation doesn't assess risk
            enforcement=enforcement
        )
    except Exception as e:
        logger.error(f"Error validating input: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating input: {str(e)}"
        )


@router.post("/validate/action", response_model=ValidationResponse)
async def validate_action(request: ActionValidationRequest):
    """
    Validate Kubernetes action for safety and permissions
    """
    record_guardrail_api_call("validate_action")
    
    try:
        # Get guardrail service
        guardrail_service = get_guardrail_service()
        
        # Perform validation
        is_valid, reason = await guardrail_service.validate_action(
            action=request.action,
            parameters=request.parameters,
            user_id=request.user_id,
            user_role=request.user_role,
            namespace=request.namespace
        )
        
        # Analyze operation risk
        operation, resource_type = guardrail_service.action_validator._parse_action(request.action)
        risk_assessment = await guardrail_service.analyze_operation_risk(
            operation=operation,
            resource_type=resource_type,
            namespace=request.namespace
        )
        
        # Get config for enforcement level
        config = get_guardrail_config()
        enforcement = config.enforcement_level
        
        return ValidationResponse(
            valid=is_valid,
            reason=reason if not is_valid else None,
            modified_content=None,  # Action validation doesn't modify content
            risk_level=risk_assessment.get("risk_level"),
            enforcement=enforcement
        )
    except Exception as e:
        logger.error(f"Error validating action: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating action: {str(e)}"
        )


@router.post("/validate/output", response_model=ValidationResponse)
async def validate_output(request: ValidationRequest):
    """
    Validate and filter LLM output
    """
    record_guardrail_api_call("validate_output")
    
    try:
        # Get guardrail service
        guardrail_service = get_guardrail_service()
        
        # Perform validation
        is_valid, reason, filtered_output = await guardrail_service.validate_llm_output(
            output=request.content,
            context=request.metadata
        )
        
        # Get config for enforcement level
        config = get_guardrail_config()
        enforcement = config.enforcement_level
        
        return ValidationResponse(
            valid=is_valid,
            reason=reason if not is_valid else None,
            modified_content=filtered_output if not is_valid else None,
            risk_level=None,  # Output validation doesn't assess risk
            enforcement=enforcement
        )
    except Exception as e:
        logger.error(f"Error validating output: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating output: {str(e)}"
        )


@router.put("/config", response_model=GuardrailStatusResponse)
async def update_guardrail_config(request: GuardrailConfigUpdateRequest):
    """
    Update guardrail configuration
    """
    record_guardrail_api_call("update_config")
    
    try:
        # Get current config
        config = get_guardrail_config()
        
        # Update fields if provided
        if request.enabled is not None:
            config.enabled = request.enabled
            
        if request.enforcement_level is not None:
            config.enforcement_level = request.enforcement_level
            
        if request.input_validation is not None:
            if "input_validation" not in config.__dict__:
                config.input_validation = {}
            config.input_validation["enabled"] = request.input_validation
            
        if request.action_validation is not None:
            if "action_validation" not in config.__dict__:
                config.action_validation = {}
            config.action_validation["enabled"] = request.action_validation
            
        if request.output_validation is not None:
            if "output_validation" not in config.__dict__:
                config.output_validation = {}
            config.output_validation["enabled"] = request.output_validation
        
        # Return updated status
        return GuardrailStatusResponse(
            enabled=config.enabled,
            enforcement_level=config.enforcement_level,
            input_validation=config.input_validation.get("enabled", True),
            action_validation=config.action_validation.get("enabled", True),
            output_validation=config.output_validation.get("enabled", True)
        )
    except Exception as e:
        logger.error(f"Error updating guardrail config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating guardrail config: {str(e)}"
        )