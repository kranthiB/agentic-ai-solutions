# monitoring/metrics_collector.py
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any
import datetime

class MetricsCollector:
    """Collects in-memory agent metrics."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.metrics = {
            "tool_calls": defaultdict(int),
            "tool_success": defaultdict(int),
            "tool_failure": defaultdict(int),
            "task_execution_times": defaultdict(list),
            "llm_tokens_used": defaultdict(int),
            "retry_counts": defaultdict(int),
            # New metrics
            "llm_input_tokens": defaultdict(int),
            "llm_output_tokens": defaultdict(int),
            "llm_calls": defaultdict(int),
            "llm_success": defaultdict(int),
            "llm_failures": defaultdict(int),
            "llm_timeouts": defaultdict(int),
            "llm_latencies": defaultdict(list),
            "prompt_lengths": defaultdict(int),
            "response_lengths": defaultdict(int),
            "task_dependencies": defaultdict(int),
            "task_dependencies_success": defaultdict(int),
            "feedback_positive": defaultdict(int),
            "feedback_negative": defaultdict(int),
            "feedback_total": defaultdict(int),
            # Metadata for enhanced labeling
            "conversation_metadata": {},
            "task_metadata": {},
        }

    def record_tool_call(self, tool_name: str, task_id: str = "unknown", conversation_id: str = "unknown"):
        self.metrics["tool_calls"][tool_name] += 1
        # Store metadata for enhanced labeling
        if task_id != "unknown":
            if tool_name not in self.metrics["task_metadata"]:
                self.metrics["task_metadata"][tool_name] = {}
            self.metrics["task_metadata"][tool_name]["task_id"] = task_id
            self.metrics["task_metadata"][tool_name]["conversation_id"] = conversation_id

    def record_tool_result(self, tool_name: str, success: bool, 
                           goal_category: str = "unknown"):
        if success:
            self.metrics["tool_success"][tool_name] += 1
        else:
            self.metrics["tool_failure"][tool_name] += 1
            
        # Store metadata for enhanced labeling
        if tool_name not in self.metrics["task_metadata"]:
            self.metrics["task_metadata"][tool_name] = {}
        self.metrics["task_metadata"][tool_name]["goal_category"] = goal_category

    def record_task_duration(self, task_id: str, start_time: float, end_time: float,
                            goal_category: str = "unknown"):
        elapsed = round(end_time - start_time, 3)
        self.metrics["task_execution_times"][task_id].append(elapsed)
        
        # Store metadata for enhanced labeling
        if task_id not in self.metrics["task_metadata"]:
            self.metrics["task_metadata"][task_id] = {}
        self.metrics["task_metadata"][task_id]["goal_category"] = goal_category
        self.metrics["task_metadata"][task_id]["hour_of_day"] = datetime.datetime.fromtimestamp(start_time).hour

    def record_llm_tokens(self, task_id: str, tokens: int, 
                         model: str = "unknown", operation_type: str = "unknown"):
        self.metrics["llm_tokens_used"][task_id] += tokens
        
        # Store metadata for enhanced labeling
        if task_id not in self.metrics["task_metadata"]:
            self.metrics["task_metadata"][task_id] = {}
        self.metrics["task_metadata"][task_id]["model"] = model
        self.metrics["task_metadata"][task_id]["operation_type"] = operation_type

    def record_retry(self, task_id: str):
        self.metrics["retry_counts"][task_id] += 1

    # New methods for enhanced metrics
    
    def record_llm_call(self, model: str, temperature: float = 0.0, 
                        operation_type: str = "unknown"):
        key = f"{model}_{temperature}_{operation_type}"
        self.metrics["llm_calls"][key] += 1
        
    def record_llm_result(self, model: str, success: bool, temperature: float = 0.0):
        key = f"{model}_{temperature}"
        if success:
            self.metrics["llm_success"][key] += 1
        else:
            self.metrics["llm_failures"][key] += 1
            
    def record_llm_timeout(self, model: str):
        self.metrics["llm_timeouts"][model] += 1
        
    def record_llm_latency(self, model: str, latency_seconds: float):
        self.metrics["llm_latencies"][model].append(latency_seconds)
        
    def record_token_details(self, task_id: str, input_tokens: int, output_tokens: int,
                           model: str = "unknown", operation_type: str = "unknown"):
        self.metrics["llm_input_tokens"][f"{task_id}_{model}_{operation_type}"] += input_tokens
        self.metrics["llm_output_tokens"][f"{task_id}_{model}_{operation_type}"] += output_tokens
        # Also update total tokens for backward compatibility
        self.metrics["llm_tokens_used"][task_id] += (input_tokens + output_tokens)
        
    def record_prompt_length(self, operation_type: str, length: int):
        self.metrics["prompt_lengths"][operation_type] = length
        
    def record_response_length(self, operation_type: str, length: int):
        self.metrics["response_lengths"][operation_type] = length
        
    def record_task_dependency(self, task_id: str, success: bool = True):
        self.metrics["task_dependencies"][task_id] += 1
        if success:
            self.metrics["task_dependencies_success"][task_id] += 1
            
    def record_feedback(self, feedback_category: str, positive: bool):
        self.metrics["feedback_total"][feedback_category] += 1
        if positive:
            self.metrics["feedback_positive"][feedback_category] += 1
        else:
            self.metrics["feedback_negative"][feedback_category] += 1
    
    def set_conversation_metadata(self, conversation_id: str, metadata: Dict[str, Any]):
        """Store metadata about a conversation for enhanced metrics labeling"""
        self.metrics["conversation_metadata"][conversation_id] = metadata
        
    def set_task_metadata(self, task_id: str, metadata: Dict[str, Any]):
        """Store metadata about a task for enhanced metrics labeling"""
        if task_id not in self.metrics["task_metadata"]:
            self.metrics["task_metadata"][task_id] = {}
        self.metrics["task_metadata"][task_id].update(metadata)

    def get_tool_summary(self) -> Dict[str, Dict[str, int]]:
        summary = {}
        for tool in self.metrics["tool_calls"]:
            summary[tool] = {
                "calls": self.metrics["tool_calls"][tool],
                "success": self.metrics["tool_success"].get(tool, 0),
                "failure": self.metrics["tool_failure"].get(tool, 0),
            }
        return summary

    def get_task_timing(self, task_id: str) -> Optional[List[float]]:
        return self.metrics["task_execution_times"].get(task_id)

    def get_metrics_snapshot(self) -> Dict:
        return self.metrics.copy()


# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector