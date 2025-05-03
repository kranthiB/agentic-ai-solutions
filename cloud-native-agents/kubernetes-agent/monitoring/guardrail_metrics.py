# monitoring/guardrail_metrics.py
import time
from typing import Dict, Any, Optional

from monitoring.metrics_collector import get_metrics_collector
from monitoring.agent_logger import get_logger
from monitoring.event_audit_log import get_audit_logger

# Initialize logging and metrics
logger = get_logger(__name__)
metrics = get_metrics_collector()
audit = get_audit_logger()


def record_guardrail_api_call(endpoint: str) -> None:
    """
    Record a guardrail API call to metrics
    
    Args:
        endpoint: API endpoint name
    """
    metrics.record_tool_call(f"guardrail_api_{endpoint}")


def record_guardrail_validation(
    validation_type: str,
    success: bool,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    conversation_id: Optional[str] = None,
    content_length: Optional[int] = None
) -> None:
    """
    Record a guardrail validation event to metrics
    
    Args:
        validation_type: Type of validation (input, action, output)
        success: Whether validation passed
        user_id: Optional user ID for categorization
        user_role: Optional user role for categorization
        conversation_id: Optional conversation ID for categorization
        content_length: Optional content length for size metrics
    """
    # Record validation result
    metrics.record_tool_result(
        f"guardrail_{validation_type}_validation",
        success
    )
    
    # Record count metrics
    if success:
        metrics.metrics[f"guardrail_{validation_type}_passed"] = \
            metrics.metrics.get(f"guardrail_{validation_type}_passed", 0) + 1
    else:
        metrics.metrics[f"guardrail_{validation_type}_blocked"] = \
            metrics.metrics.get(f"guardrail_{validation_type}_blocked", 0) + 1
    
    # Set metadata if available
    if user_id or user_role or conversation_id:
        metrics.set_task_metadata(
            f"guardrail_{validation_type}_validation",
            {
                "user_id": user_id,
                "user_role": user_role,
                "conversation_id": conversation_id
            }
        )
    
    # Record content length if available
    if content_length is not None:
        key = f"guardrail_{validation_type}_content_length"
        if key not in metrics.metrics:
            metrics.metrics[key] = []
        metrics.metrics[key].append(content_length)


def record_guardrail_block(
    block_type: str,
    reason: str,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    action: Optional[str] = None,
    namespace: Optional[str] = None
) -> None:
    """
    Record a guardrail block event to metrics and audit log
    
    Args:
        block_type: Type of block (input, action, output)
        reason: Reason for the block
        user_id: Optional user ID
        user_role: Optional user role
        action: Optional action (for action blocks)
        namespace: Optional namespace (for action blocks)
    """
    # Record block count
    key = f"guardrail_block_{block_type}"
    metrics.metrics[key] = metrics.metrics.get(key, 0) + 1
    
    # Categorize by reason
    reason_key = f"guardrail_block_reason_{reason.replace(' ', '_')}"
    metrics.metrics[reason_key] = metrics.metrics.get(reason_key, 0) + 1
    
    # Log to audit log
    audit.log_event(f"guardrail_block_{block_type}", {
        "reason": reason,
        "user_id": user_id,
        "user_role": user_role,
        "action": action,
        "namespace": namespace
    })


def record_guardrail_latency(
    validation_type: str,
    start_time: float,
    end_time: float
) -> None:
    """
    Record guardrail validation latency
    
    Args:
        validation_type: Type of validation (input, action, output)
        start_time: Start time of validation
        end_time: End time of validation
    """
    # Calculate latency
    latency = end_time - start_time
    
    # Record to metrics
    metrics.record_task_duration(
        f"guardrail_{validation_type}_validation",
        start_time,
        end_time
    )
    
    # Store in latency list for histogram
    key = f"guardrail_{validation_type}_latency"
    if key not in metrics.metrics:
        metrics.metrics[key] = []
    metrics.metrics[key].append(latency)


def record_risk_assessment(
    operation: str,
    resource_type: str,
    namespace: str,
    risk_level: str
) -> None:
    """
    Record a risk assessment
    
    Args:
        operation: Operation type
        resource_type: Resource type
        namespace: Kubernetes namespace
        risk_level: Assessed risk level
    """
    # Record count by risk level
    key = f"guardrail_risk_{risk_level}"
    metrics.metrics[key] = metrics.metrics.get(key, 0) + 1
    
    # Record operation-specific risk
    op_key = f"guardrail_risk_{operation}_{resource_type}"
    metrics.metrics[op_key] = metrics.metrics.get(op_key, 0) + 1
    
    # Log high-risk operations to audit log
    if risk_level == "high":
        audit.log_event("high_risk_operation", {
            "operation": operation,
            "resource_type": resource_type,
            "namespace": namespace,
            "risk_level": risk_level
        })


def get_guardrail_metrics() -> Dict[str, Any]:
    """
    Get a summary of guardrail-related metrics
    
    Returns:
        Dict with guardrail metrics
    """
    metrics_snapshot = metrics.get_metrics_snapshot()
    guardrail_metrics = {}
    
    # Extract guardrail-specific metrics
    for key, value in metrics_snapshot.items():
        if key.startswith("guardrail_"):
            guardrail_metrics[key] = value
    
    return guardrail_metrics