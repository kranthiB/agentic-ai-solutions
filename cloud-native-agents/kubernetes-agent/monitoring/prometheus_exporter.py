# monitoring/prometheus_exporter.py
"""
Usage

from monitoring.prometheus_exporter import start_metrics_export

start_metrics_export()
"""
import yaml
import threading
import time
import os
import datetime

from prometheus_client import Gauge, Counter, Histogram, push_to_gateway
from monitoring.metrics_collector import get_metrics_collector
from monitoring.cost_tracker import get_cost_tracker
from monitoring.agent_logger import get_logger

# Default values (fallback)
DEFAULT_CONFIG = {
    "enabled": True,
    "update_interval_seconds": 10,
    "metrics": {
        "track_tokens": True,
        "track_cost": True,
        "track_retries": True
    },
    "push_gateway": "localhost:9091"  # Prometheus running in Docker Compose
}

def load_prometheus_config(config_path: str = "configs/prometheus_config.yaml") -> dict:
    logger = get_logger(__name__)
    if not os.path.exists(config_path):
        logger.warning(f"Config file {config_path} not found. Using defaults.")
        return DEFAULT_CONFIG
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# Basic metric definitions
TOOL_CALLS = Counter("agent_tool_calls_total", "Total tool calls", ["tool_name", "task_id", "conversation_id"])
TOOL_SUCCESS = Counter("agent_tool_success_total", "Successful tool calls", ["tool_name", "task_id", "goal_category"])
TOOL_FAILURE = Counter("agent_tool_failure_total", "Failed tool calls", ["tool_name", "task_id", "goal_category"])

# Task-related metrics
TASK_EXEC_TIME = Gauge("agent_task_execution_time_seconds", "Task execution time (avg)", 
                       ["task_id", "goal_category", "hour_of_day"])
TASK_DURATION = Histogram("agent_task_duration_seconds", "Task duration distribution",
                         ["task_id", "goal_category"], buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600])
TASK_DEPENDENCY_SUCCESS = Counter("agent_task_dependency_success", "Successful task dependencies", ["task_id"])
TASK_DEPENDENCY_TOTAL = Counter("agent_task_dependency_total", "Total task dependencies", ["task_id"])

# LLM-related metrics
LLM_TOKENS = Counter("agent_llm_tokens_total", "LLM tokens used", ["task_id", "model", "operation_type"])
LLM_INPUT_TOKENS = Counter("agent_llm_input_tokens_total", "LLM input tokens", ["task_id", "model", "operation_type"])
LLM_OUTPUT_TOKENS = Counter("agent_llm_output_tokens_total", "LLM output tokens", ["task_id", "model", "operation_type"])
LLM_COST = Gauge("agent_llm_cost_usd", "Estimated LLM cost", ["task_id", "model", "operation_type"])
LLM_PROMPT_LENGTH = Gauge("agent_llm_prompt_length", "Length of prompts sent to LLM", ["operation_type"])
LLM_RESPONSE_LENGTH = Gauge("agent_llm_response_length", "Length of responses from LLM", ["operation_type"])
LLM_CALLS = Counter("agent_llm_calls_total", "Total LLM API calls", ["model", "temperature", "operation_type"])
LLM_SUCCESS = Counter("agent_llm_success_total", "Successful LLM API calls", ["model", "temperature"])
LLM_TIMEOUTS = Counter("agent_llm_timeouts_total", "LLM API call timeouts", ["model"])
LLM_LATENCY = Histogram("agent_llm_latency_seconds", "LLM API call latency", 
                       ["model"], buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60])

# Retry and reliability metrics
RETRY_COUNT = Counter("agent_retry_total", "Retries per task", ["task_id"])

# Feedback metrics
FEEDBACK_POSITIVE = Counter("agent_feedback_positive", "Positive user feedback", ["feedback_category"])
FEEDBACK_NEGATIVE = Counter("agent_feedback_negative", "Negative user feedback", ["feedback_category"])
FEEDBACK_TOTAL = Counter("agent_feedback_total", "Total user feedback", ["feedback_category"])

def update_metrics_and_push(push_gateway_url, job_name="kubernetes_agent", update_interval=10):
    logger = get_logger(__name__)
    metrics = get_metrics_collector()
    cost = get_cost_tracker()

    while True:
        try:
            # Get current time info for time-based metrics
            current_hour = datetime.datetime.now().hour
            hour_label = f"{current_hour:02d}:00"
            
            snapshot = metrics.get_metrics_snapshot()

            # Process tool metrics
            for tool, count in snapshot["tool_calls"].items():
                # Default fallback for labels
                task_id = "unknown"
                conversation_id = "unknown"
                
                # Add tool call metrics with enhanced labels
                TOOL_CALLS.labels(tool_name=tool, task_id=task_id, conversation_id=conversation_id).inc(count)

            for tool, count in snapshot["tool_success"].items():
                TOOL_SUCCESS.labels(tool_name=tool, task_id="unknown", goal_category="unknown").inc(count)

            for tool, count in snapshot["tool_failure"].items():
                TOOL_FAILURE.labels(tool_name=tool, task_id="unknown", goal_category="unknown").inc(count)

            # Process task timing metrics
            for task_id, durations in snapshot["task_execution_times"].items():
                if durations:
                    avg = sum(durations) / len(durations)
                    # Use fallback for missing labels
                    TASK_EXEC_TIME.labels(task_id=task_id, goal_category="unknown", hour_of_day=hour_label).set(avg)
                    
                    # Add to histogram for better distribution analysis
                    for duration in durations:
                        TASK_DURATION.labels(task_id=task_id, goal_category="unknown").observe(duration)

            # Process token usage with model and operation type
            for task_id, tokens in snapshot["llm_tokens_used"].items():
                # Default labels when specifics aren't available
                model = "unknown"
                operation_type = "unknown"
                
                # Add with available labels
                LLM_TOKENS.labels(task_id=task_id, model=model, operation_type=operation_type).inc(tokens)
                
                # Estimate input/output split (typically 70/30 for most LLMs)
                input_tokens = int(tokens * 0.7)  # Approximate
                output_tokens = tokens - input_tokens
                
                LLM_INPUT_TOKENS.labels(task_id=task_id, model=model, operation_type=operation_type).inc(input_tokens)
                LLM_OUTPUT_TOKENS.labels(task_id=task_id, model=model, operation_type=operation_type).inc(output_tokens)

            # Process retry metrics
            for task_id, count in snapshot["retry_counts"].items():
                RETRY_COUNT.labels(task_id=task_id).inc(count)

            # Process cost metrics with enhanced labels
            for task_id, models in cost.get_breakdown().items():
                for model, cost_val in models.items():
                    LLM_COST.labels(task_id=task_id, model=model, operation_type="unknown").set(cost_val)

            # Push metrics to Prometheus Gateway
            try:
                push_to_gateway(push_gateway_url, job=job_name, registry=None)  # None uses the default registry
                logger.debug(f"Successfully pushed metrics to gateway at {push_gateway_url}")
            except Exception as e:
                logger.error(f"Failed to push metrics to gateway: {str(e)}")

            # Clear the collected metrics to avoid double-counting
            metrics.reset()

        except Exception as e:
            logger.error(f"Error in metrics processing: {str(e)}")
        
        # Sleep before next update
        time.sleep(update_interval)

def start_metrics_export(config_path: str = "configs/prometheus_config.yaml"):
    logger = get_logger(__name__)
    cfg = load_prometheus_config(config_path)
    prometheus_cfg = cfg.get("prometheus", DEFAULT_CONFIG)
    
    if not prometheus_cfg.get("enabled", True):
        logger.info("🚫 Prometheus metrics export is disabled via config.")
        return

    # Use the Docker Compose service name and port for Prometheus
    push_gateway_url = prometheus_cfg.get("push_gateway", "localhost:9091")
    interval = prometheus_cfg.get("update_interval_seconds", 10)

    logger.info(f"🚀 Starting metrics export to Prometheus at {push_gateway_url}")
    threading.Thread(
        target=update_metrics_and_push, 
        args=(push_gateway_url, "kubernetes_agent", interval), 
        daemon=True
    ).start()