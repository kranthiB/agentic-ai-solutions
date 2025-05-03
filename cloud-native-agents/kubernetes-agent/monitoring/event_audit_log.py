# monitoring/event_audit_log.py
"""
Usage

from monitoring.event_audit_log import get_audit_logger

audit = get_audit_logger()

audit.log_plan_created(plan_id, user_goal="Restart failing pods", num_tasks=3)

audit.log_task_execution(plan_id, task_id, "Check pod logs in namespace 'prod'")

audit.log_tool_invoked(task_id, "get_pod_logs", {"pod_name": "nginx-123", "namespace": "prod"})

audit.log_tool_result(task_id, "get_pod_logs", result=truncated_output, success=True)

audit.log_feedback(task_id, "thumbs", "positive", None)

Stored

Stored at: logs/audit/<session_id>.jsonl
"""
import json
import os
from datetime import datetime
import re
from typing import Dict, Any, Optional
from monitoring.metrics_collector import get_metrics_collector


class EventAuditLog:
    """Writes a structured event log to a JSONL file per session."""

    def __init__(self, session_id: Optional[str] = None, log_dir: str = "logs/audit"):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.file_path = os.path.join(log_dir, f"{self.session_id}.jsonl")
        self.metrics = get_metrics_collector()  # Get metrics collector for integration

    def log_event(self, event_type: str, metadata: Dict[str, Any]):
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "metadata": metadata
        }
        with open(self.file_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def log_plan_created(self, plan_id: str, user_goal: str, num_tasks: int, goal_category: str = "general"):
        metadata = {
            "plan_id": plan_id,
            "user_goal": user_goal,
            "task_count": num_tasks,
            "goal_category": goal_category
        }
        self.log_event("plan_created", metadata)
        
        # Update metrics metadata for enhanced labels
        self.metrics.set_task_metadata(plan_id, {
            "goal_category": goal_category,
            "task_count": num_tasks
        })

    def log_task_execution(self, plan_id: str, task_id: str, task_text: str, 
                           goal_category: str = "general", priority: int = 1):
        metadata = {
            "plan_id": plan_id,
            "task_id": task_id,
            "task": task_text,
            "goal_category": goal_category,
            "priority": priority,
            "hour_of_day": datetime.now().hour  # Add time dimension
        }
        self.log_event("task_started", metadata)
        
        # Update metrics metadata for enhanced labels
        self.metrics.set_task_metadata(task_id, {
            "plan_id": plan_id,
            "goal_category": goal_category,
            "hour_of_day": datetime.now().hour,
            "priority": priority
        })

    def log_tool_invoked(self, task_id: str, tool_name: str, params: Dict[str, Any], 
                         conversation_id: str = "unknown"):
        metadata = {
            "task_id": task_id,
            "tool_name": tool_name,
            "parameters": params,
            "conversation_id": conversation_id
        }
        self.log_event("tool_invoked", metadata)
        
        # Record tool call in metrics with enhanced labels
        self.metrics.record_tool_call(tool_name, task_id, conversation_id)

    def log_tool_result(self, task_id: str, tool_name: str, result: Any, success: bool, 
                       goal_category: str = "general"):
        # Truncate large results to avoid massive logs
        result_str = str(result)
        if len(result_str) > 1000:
            result_str = result_str[:997] + "..."
            
        metadata = {
            "task_id": task_id,
            "tool_name": tool_name,
            "success": success,
            "result": result_str,
            "goal_category": goal_category
        }
        self.log_event("tool_result", metadata)
        
        # Record tool result in metrics with enhanced labels
        self.metrics.record_tool_result(tool_name, success, goal_category)

    def log_retry(self, task_id: str, reason: str):
        metadata = {
            "task_id": task_id,
            "reason": reason
        }
        self.log_event("task_retry", metadata)
        
        # Record retry in metrics
        self.metrics.record_retry(task_id)

    def log_feedback(self, task_id: str, feedback_type: str, result: str, 
                     free_text: Optional[str], category: str = "general"):
        metadata = {
            "task_id": task_id,
            "type": feedback_type,
            "result": result,
            "comment": free_text,
            "category": category
        }
        self.log_event("feedback_collected", metadata)
        
        # Record feedback in metrics
        is_positive = result.lower() in ["positive", "thumbs_up", "like", "yes", "good"]
        self.metrics.record_feedback(category, is_positive)
    
    def log_llm_interaction(self, task_id: str, model: str, input_tokens: int, 
                          output_tokens: int, latency: float, success: bool,
                          operation_type: str = "general", temperature: float = 0.0):
        """Log detailed information about an LLM interaction for metrics collection"""
        metadata = {
            "task_id": task_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_seconds": latency,
            "success": success,
            "operation_type": operation_type,
            "temperature": temperature
        }
        self.log_event("llm_interaction", metadata)
        
        # Record all the relevant metrics
        self.metrics.record_token_details(task_id, input_tokens, output_tokens, model, operation_type)
        self.metrics.record_llm_call(model, temperature, operation_type)
        self.metrics.record_llm_result(model, success, temperature)
        self.metrics.record_llm_latency(model, latency)
        
        if not success:
            # Check if it's a timeout (latency > 30s is typically a timeout)
            if latency > 30:
                self.metrics.record_llm_timeout(model)

    # NEW: Guardrail-specific audit events
    def log_guardrail_validation(self, 
                               validation_type: str, 
                               input_content: str, 
                               is_valid: bool, 
                               reason: Optional[str] = None,
                               user_id: str = "system",
                               conversation_id: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None):
        """
        Log a guardrail validation event
        
        Args:
            validation_type: Type of validation (input, action, output)
            input_content: Content that was validated (truncated for privacy)
            is_valid: Whether validation passed
            reason: Reason for failure if not valid
            user_id: ID of the user or component that triggered validation
            conversation_id: Optional conversation context
            metadata: Additional context information
        """
        # Truncate and sanitize input for privacy
        truncated_input = self._sanitize_content(input_content)
        
        audit_metadata = {
            "validation_type": validation_type,
            "is_valid": is_valid,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id
        }
        
        # Only include reason if validation failed
        if not is_valid and reason:
            audit_metadata["reason"] = reason
            
        # Add truncated input preview
        audit_metadata["content_preview"] = truncated_input
        
        # Add any additional metadata
        if metadata:
            audit_metadata.update(metadata)
        
        # Log the event
        self.log_event(f"guardrail_{validation_type}_validation", audit_metadata)
        
        # Record in metrics
        self.metrics.record_tool_result(
            f"guardrail_{validation_type}_validation", 
            is_valid
        )
        
        # Record validation count
        if is_valid:
            self.metrics.metrics[f"guardrail_{validation_type}_passed"] = \
                self.metrics.metrics.get(f"guardrail_{validation_type}_passed", 0) + 1
        else:
            self.metrics.metrics[f"guardrail_{validation_type}_blocked"] = \
                self.metrics.metrics.get(f"guardrail_{validation_type}_blocked", 0) + 1

    def log_guardrail_block(self, 
                          block_type: str, 
                          reason: str,
                          content_preview: str,
                          user_id: str = "system",
                          conversation_id: Optional[str] = None,
                          action: Optional[str] = None,
                          resource_type: Optional[str] = None,
                          namespace: Optional[str] = None):
        """
        Log a guardrail block event when content is blocked
        
        Args:
            block_type: Type of block (input, action, output)
            reason: Reason for the block
            content_preview: Sanitized preview of blocked content
            user_id: User identifier
            conversation_id: Optional conversation context
            action: Optional action name (for action blocks)
            resource_type: Optional resource type (for action blocks)
            namespace: Optional namespace (for action blocks)
        """
        metadata = {
            "block_type": block_type,
            "reason": reason,
            "content_preview": content_preview,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add conversation ID if available
        if conversation_id:
            metadata["conversation_id"] = conversation_id
            
        # Add action details if available
        if action:
            metadata["action"] = action
        if resource_type:
            metadata["resource_type"] = resource_type
        if namespace:
            metadata["namespace"] = namespace
            
        # Log the event
        self.log_event("guardrail_block", metadata)
        
        # Record block in metrics
        self.metrics.metrics[f"guardrail_block_{block_type}"] = \
            self.metrics.metrics.get(f"guardrail_block_{block_type}", 0) + 1
            
        # Categorize by reason
        reason_key = f"guardrail_block_reason_{reason.replace(' ', '_')}"
        self.metrics.metrics[reason_key] = self.metrics.metrics.get(reason_key, 0) + 1

    def log_guardrail_risk_assessment(self,
                                    operation: str,
                                    resource_type: str,
                                    namespace: str,
                                    risk_level: str,
                                    requires_approval: bool,
                                    conversation_id: Optional[str] = None,
                                    user_id: str = "system"):
        """
        Log a risk assessment for an operation
        
        Args:
            operation: Operation being assessed (e.g., delete, scale)
            resource_type: Resource type (e.g., pod, deployment)
            namespace: Kubernetes namespace
            risk_level: Assessed risk level (low, medium, high)
            requires_approval: Whether explicit approval is required
            conversation_id: Optional conversation context
            user_id: User identifier
        """
        metadata = {
            "operation": operation,
            "resource_type": resource_type,
            "namespace": namespace,
            "risk_level": risk_level,
            "requires_approval": requires_approval,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add conversation ID if available
        if conversation_id:
            metadata["conversation_id"] = conversation_id
            
        # Log the event
        self.log_event("guardrail_risk_assessment", metadata)
        
        # Record in metrics
        self.metrics.metrics[f"guardrail_risk_{risk_level}"] = \
            self.metrics.metrics.get(f"guardrail_risk_{risk_level}", 0) + 1
            
        # Record operation-specific risk
        op_key = f"guardrail_risk_{operation}_{resource_type}"
        self.metrics.metrics[op_key] = self.metrics.metrics.get(op_key, 0) + 1
        
        # Record high-risk operations
        if risk_level == "high":
            high_risk_key = "guardrail_high_risk_operations"
            self.metrics.metrics[high_risk_key] = self.metrics.metrics.get(high_risk_key, 0) + 1

    def log_guardrail_approval(self,
                             approved: bool,
                             operation: str,
                             resource_type: str,
                             namespace: str,
                             conversation_id: Optional[str] = None,
                             user_id: str = "system"):
        """
        Log an approval decision for a high-risk operation
        
        Args:
            approved: Whether the operation was approved
            operation: Operation type (e.g., delete, scale)
            resource_type: Resource type (e.g., pod, deployment)
            namespace: Kubernetes namespace
            conversation_id: Optional conversation context
            user_id: User identifier
        """
        metadata = {
            "approved": approved,
            "operation": operation,
            "resource_type": resource_type,
            "namespace": namespace,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add conversation ID if available
        if conversation_id:
            metadata["conversation_id"] = conversation_id
            
        # Log the event
        self.log_event("guardrail_approval", metadata)
        
        # Record in metrics
        if approved:
            self.metrics.metrics["guardrail_approvals"] = \
                self.metrics.metrics.get("guardrail_approvals", 0) + 1
        else:
            self.metrics.metrics["guardrail_rejections"] = \
                self.metrics.metrics.get("guardrail_rejections", 0) + 1

    def _sanitize_content(self, content: str, max_length: int = 100) -> str:
        """
        Create a sanitized preview of content for logging
        
        Args:
            content: Original content
            max_length: Maximum length for the preview
            
        Returns:
            Sanitized content preview
        """
        if not content:
            return "<empty>"
            
        # Truncate
        if len(content) > max_length:
            preview = content[:max_length] + "..."
        else:
            preview = content
            
        # Remove potentially sensitive information
        sanitized = preview
        # Remove email patterns
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)
        # Remove IP address patterns
        sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', sanitized)
        # Remove token patterns
        sanitized = re.sub(r'(?:token|bearer|api[_-]?key)[^\w\s]*[=:][^\w\s]*[\w\d-._~+/]+', '[TOKEN]', sanitized, flags=re.IGNORECASE)
        # Remove password patterns
        sanitized = re.sub(r'(?:password|pwd|passwd)[^\w\s]*[=:][^\w\s]*[^\s]+', '[PASSWORD]', sanitized, flags=re.IGNORECASE)
        
        return sanitized


# Singleton access
_audit_logger: Optional[EventAuditLog] = None

def get_audit_logger(session_id: Optional[str] = None) -> EventAuditLog:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = EventAuditLog(session_id=session_id)
    return _audit_logger