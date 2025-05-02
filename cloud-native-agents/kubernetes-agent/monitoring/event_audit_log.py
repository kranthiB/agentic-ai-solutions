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


# Singleton access
_audit_logger: Optional[EventAuditLog] = None

def get_audit_logger(session_id: Optional[str] = None) -> EventAuditLog:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = EventAuditLog(session_id=session_id)
    return _audit_logger