import time
import random
import requests
import datetime
import uuid
from collections import defaultdict

# Pushgateway URL
PUSHGATEWAY_URL = "http://localhost:9091"

# Common job name - make this unique for each run
JOB_NAME = f"kubernetes_agent_{int(time.time())}"

# Kubernetes-specific tools
k8s_tools = [
    "kubectl_tool", 
    "config_tool", 
    "configmap_tool", 
    "deployment_tool", 
    "logging_tool", 
    "namespace_tool", 
    "node_tool", 
    "pod_tool", 
    "resource_tool", 
    "security_tool", 
    "services_tool"
]

# LLM models with estimated costs per 1K tokens
llm_models = {
    "claude-3-5-sonnet-20241022": 0.03,
    "claude-3-7-sonnet-20250219": 0.05,
    "gpt-4o": 0.04,
    "gpt-4": 0.06,
    "gemini-2.5-pro": 0.025
}

# Kubernetes operation types
operation_types = [
    "cluster_management",
    "deployment_management",
    "configuration_management",
    "resource_scaling",
    "logging_analysis",
    "security_auditing",
    "namespace_management",
    "pod_management",
    "service_management",
    "node_management"
]

# Goal categories for Kubernetes operations
goal_categories = [
    "cluster_optimization", 
    "deployment_automation", 
    "security_compliance", 
    "resource_management", 
    "monitoring_setup", 
    "troubleshooting", 
    "disaster_recovery"
]

# Task priorities
priorities = ["high", "medium", "low"]

# Temperature settings for LLM
temperature_settings = ["0.0", "0.2", "0.5", "0.7", "1.0"]

def push_metrics(metrics):
    """Push multiple metrics to the Pushgateway at once"""
    # Build the full payload
    payload = ""
    for metric in metrics:
        name = metric["name"]
        value = metric["value"]
        labels = metric.get("labels", {})
        
        # Add job label
        labels["job"] = JOB_NAME
        # Add instance label (required by Prometheus)
        labels["instance"] = "simulator"
        
        # Build label string
        if labels:
            label_str = "{" + ",".join([f'{k}="{v}"' for k, v in labels.items()]) + "}"
        else:
            label_str = ""
        
        # Add this metric line to the payload
        payload += f'{name}{label_str} {value}\n'
    
    # Send all metrics at once
    try:
        response = requests.post(
            f"{PUSHGATEWAY_URL}/metrics/job/{JOB_NAME}",
            data=payload
        )
        
        if response.status_code != 200:
            print(f"Failed to push metrics: {response.text}")
            print(f"Payload sample: {payload[:200]}...")
        else:
            print(f"Successfully pushed {len(metrics)} metrics to Pushgateway")
    except Exception as e:
        print(f"Error pushing metrics: {e}")

def delete_previous_metrics():
    """Delete any previous metrics with the same job name"""
    try:
        requests.delete(f"{PUSHGATEWAY_URL}/metrics/job/{JOB_NAME}")
        print(f"Deleted previous metrics for job {JOB_NAME}")
    except Exception as e:
        print(f"Error deleting previous metrics: {e}")

def generate_cost_management():
    """Generate cost management metrics for Kubernetes operations"""
    print("\nGenerating Cost Management metrics...")
    metrics = []
    
    # Daily LLM Cost data
    now = int(time.time())
    for day in range(30):
        day_timestamp = now - (day * 86400)
        day_str = datetime.datetime.fromtimestamp(day_timestamp).strftime("%Y-%m-%d")
        day_cost = random.uniform(0.1, 2.0)  # Daily cost between $0.10 and $2.00
        
        metrics.append({
            "name": "agent_llm_cost_usd",
            "value": day_cost,
            "labels": {"day": day_str, "metric_type": "daily_cost"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Top token-heavy tasks
    metrics = []
    for i in range(10):
        task_id = f"task_heavy_{i}"
        token_count = random.randint(500, 5000)
        model = random.choice(list(llm_models.keys()))
        
        metrics.append({
            "name": "agent_llm_tokens_total",
            "value": token_count,
            "labels": {"task_id": task_id, "model": model}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Projected monthly cost
    metrics = []
    last_7_days_cost = random.uniform(3, 15)
    projected_monthly = (last_7_days_cost / 7) * 30
    
    metrics.append({
        "name": "agent_llm_cost_usd",
        "value": last_7_days_cost,
        "labels": {"timeframe": "last_7_days", "metric_type": "cost_timeframe"}
    })
    metrics.append({
        "name": "agent_llm_cost_usd",
        "value": projected_monthly,
        "labels": {"timeframe": "projected_monthly", "metric_type": "cost_projection"}
    })
    
    # Average cost per conversation
    total_cost = random.uniform(5, 20)
    conversation_count = random.randint(50, 200)
    avg_cost_per_conversation = total_cost / conversation_count
    
    metrics.append({
        "name": "agent_llm_cost_usd",
        "value": total_cost,
        "labels": {"metric": "total_cost", "metric_type": "total_cost"}
    })
    metrics.append({
        "name": "agent_task_execution_time_seconds_count",
        "value": conversation_count,
        "labels": {"task_id": "conversation_total", "metric_type": "conversation_count"}
    })
    metrics.append({
        "name": "agent_conversation_avg_cost",
        "value": avg_cost_per_conversation,
        "labels": {"metric_type": "avg_cost_per_conversation"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Top expensive operations
    metrics = []
    for i in range(20):
        task_id = f"task_expensive_{i}"
        model = random.choice(list(llm_models.keys()))
        operation_cost = random.uniform(0.01, 0.5)
        
        metrics.append({
            "name": "agent_llm_cost_usd",
            "value": operation_cost,
            "labels": {"task_id": task_id, "model": model, "metric_type": "operation_cost"}
        })
    
    # Cost optimization opportunities
    for i in range(10):
        task_id = f"task_optimization_{i}"
        model = random.choice(list(llm_models.keys()))
        potential_saving = random.uniform(0.01, 0.2)
        
        metrics.append({
            "name": "agent_llm_cost_usd",
            "value": potential_saving,
            "labels": {"task_id": task_id, "model": model, "optimizable": "true", "metric_type": "potential_savings"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_llm_operations():
    """Generate LLM operations metrics for Kubernetes tools"""
    print("\nGenerating LLM Operations metrics...")
    
    # Model performance comparison
    metrics = []
    for model in llm_models.keys():
        call_count = random.randint(100, 1000)
        
        # Different models have different success rates
        if "claude-3-7" in model or "gpt-4o" in model:
            success_rate = random.uniform(0.95, 0.99)
        else:
            success_rate = random.uniform(0.90, 0.97)
            
        latency = random.uniform(0.5, 3.0)
        tokens = random.randint(10000, 100000)
        cost = (tokens / 1000) * llm_models[model]
        
        metrics.append({
            "name": "agent_llm_calls_total",
            "value": call_count,
            "labels": {"model": model, "metric_type": "model_calls"}
        })
        metrics.append({
            "name": "agent_llm_success_total",
            "value": int(call_count * success_rate),
            "labels": {"model": model, "metric_type": "model_success"}
        })
        metrics.append({
            "name": "agent_llm_latency_seconds",
            "value": latency,
            "labels": {"model": model, "metric_type": "model_latency"}
        })
        metrics.append({
            "name": "agent_llm_tokens_total",
            "value": tokens,
            "labels": {"model": model, "metric_type": "model_tokens"}
        })
        metrics.append({
            "name": "agent_llm_cost_usd",
            "value": cost,
            "labels": {"model": model, "metric_type": "model_cost"}
        })
        metrics.append({
            "name": "agent_llm_cost_per_1k_tokens",
            "value": cost / (tokens / 1000),
            "labels": {"model": model, "metric_type": "cost_per_1k"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Prompt length analysis
    metrics = []
    for i, op_type in enumerate(operation_types):
        prompt_length = random.randint(50, 3000)
        metrics.append({
            "name": "agent_llm_prompt_length",
            "value": prompt_length,
            "labels": {"operation_type": op_type, "metric_id": str(i)}
        })
    
    # Response size distribution
    for i, op_type in enumerate(operation_types):
        response_length = random.randint(100, 2000)
        metrics.append({
            "name": "agent_llm_response_length",
            "value": response_length,
            "labels": {"operation_type": op_type, "metric_id": str(i)}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Temperature effect analysis
    metrics = []
    for temp in temperature_settings:
        call_count = random.randint(100, 1000)
        success_count = int(call_count * random.uniform(0.85, 0.99))
        
        metrics.append({
            "name": "agent_llm_calls_total",
            "value": call_count,
            "labels": {"temperature": temp, "metric_type": "temp_calls"}
        })
        metrics.append({
            "name": "agent_llm_success_total",
            "value": success_count,
            "labels": {"temperature": temp, "metric_type": "temp_success"}
        })
    
    # Fallback mechanism usage
    now = int(time.time())
    for hour in range(24):
        timestamp = now - (hour * 3600)
        fallback_count = random.randint(0, 5)
        
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": fallback_count,
            "labels": {
                "tool_name": "fallback_llm",
                "hour": str(hour),
                "metric_type": "fallback_usage"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Token usage optimization opportunities
    metrics = []
    for i, op_type in enumerate(operation_types):
        token_usage = random.randint(1000, 20000)
        cost = (token_usage / 1000) * random.uniform(0.002, 0.06)
        potential_savings = cost * 0.3  # 30% potential savings
        
        metrics.append({
            "name": "agent_llm_tokens_total",
            "value": token_usage,
            "labels": {"operation_type": op_type, "metric_id": f"opt_{i}", "metric_type": "token_usage"}
        })
        metrics.append({
            "name": "agent_llm_cost_usd",
            "value": cost,
            "labels": {"operation_type": op_type, "metric_id": f"opt_{i}", "metric_type": "token_cost"}
        })
        metrics.append({
            "name": "agent_llm_potential_savings",
            "value": potential_savings,
            "labels": {"operation_type": op_type, "metric_id": f"opt_{i}", "metric_type": "potential_savings"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_operations_overview():
    """Generate operations overview metrics for Kubernetes tools"""
    print("\nGenerating Operations Overview metrics...")
    metrics = []
    
    # Tasks status
    completed_tasks = random.randint(50, 150)
    failed_tasks = random.randint(5, 30)
    in_progress_tasks = random.randint(5, 20)
    
    metrics.append({
        "name": "agent_tool_success_total",
        "value": completed_tasks,
        "labels": {"task_id": "task_summary", "status": "completed"}
    })
    metrics.append({
        "name": "agent_tool_failure_total",
        "value": failed_tasks,
        "labels": {"task_id": "task_summary", "status": "failed"}
    })
    metrics.append({
        "name": "agent_task_in_progress",
        "value": in_progress_tasks,
        "labels": {"task_id": "task_summary", "status": "in_progress"}
    })
    
    # Average conversation completion time
    avg_completion_time = random.uniform(60, 180)
    metrics.append({
        "name": "agent_task_execution_time_seconds",
        "value": avg_completion_time,
        "labels": {"task_id": "total_conversation", "metric_type": "avg_completion"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Day-over-day metrics
    metrics = []
    today_calls = random.randint(500, 1000)
    yesterday_calls = random.randint(400, 900)
    change_pct = ((today_calls - yesterday_calls) / yesterday_calls) * 100
    
    metrics.append({
        "name": "agent_tool_calls_total",
        "value": today_calls,
        "labels": {"period": "today", "metric_type": "daily_calls"}
    })
    metrics.append({
        "name": "agent_tool_calls_total",
        "value": yesterday_calls,
        "labels": {"period": "yesterday", "metric_type": "daily_calls"}
    })
    metrics.append({
        "name": "agent_metric_change_percent",
        "value": change_pct,
        "labels": {"metric": "tool_calls", "metric_type": "daily_change"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_conversation_analytics():
    """Generate conversation analytics metrics"""
    print("\nGenerating Conversation Analytics metrics...")
    metrics = []
    
    # Average conversation length
    avg_length = random.uniform(60, 300)
    metrics.append({
        "name": "agent_task_execution_time_seconds",
        "value": avg_length,
        "labels": {"task_id": "total_conversation", "metric_type": "avg_length"}
    })
    
    # Conversation completion rate
    success_count = random.randint(80, 100)
    total_count = 100
    metrics.append({
        "name": "agent_tool_success_total",
        "value": success_count,
        "labels": {"task_id": "conversation_total", "metric_type": "success_count"}
    })
    metrics.append({
        "name": "agent_task_execution_time_seconds_count",
        "value": total_count,
        "labels": {"task_id": "conversation_total", "metric_type": "total_count"}
    })
    metrics.append({
        "name": "agent_conversation_completion_rate",
        "value": (success_count / total_count) * 100,
        "labels": {"metric_type": "completion_rate"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Average tasks per conversation
    metrics = []
    conversation_task_counts = []
    for conv_id in range(1, 30):
        conversation_id = f"conversation_{conv_id}"
        task_count = random.randint(3, 15)
        conversation_task_counts.append(task_count)
        
        for task_id in range(1, task_count + 1):
            tool = random.choice(k8s_tools)
            metrics.append({
                "name": "agent_tool_calls_total",
                "value": 1,
                "labels": {
                    "task_id": f"task_{task_id}",
                    "conversation_id": conversation_id,
                    "tool_name": tool,
                    "metric_type": "task_in_conversation"
                }
            })
    
    # Calculate and push the average tasks per conversation
    avg_tasks = sum(conversation_task_counts) / len(conversation_task_counts) if conversation_task_counts else 0
    metrics.append({
        "name": "agent_conversation_avg_tasks",
        "value": avg_tasks,
        "labels": {"metric_type": "avg_tasks_per_conversation"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Peak usage times
    metrics = []
    now = int(time.time())
    for hour in range(24):
        hour_of_day = hour  # 0-23
        
        # More conversations during business hours
        if 9 <= hour_of_day <= 17:
            rate_multiplier = 2.0
        else:
            rate_multiplier = 1.0
            
        conversation_rate = random.uniform(0.01, 0.1) * rate_multiplier
        
        metrics.append({
            "name": "agent_conversation_rate",
            "value": conversation_rate,
            "labels": {
                "hour": str(hour_of_day),
                "metric_type": "hourly_rate"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Goal categories breakdown
    metrics = []
    for category in goal_categories:
        category_count = random.randint(10, 100)
        metrics.append({
            "name": "agent_task_execution_time_seconds_count",
            "value": category_count,
            "labels": {
                "task_id": "conversation_category",
                "goal_category": category,
                "metric_type": "category_count"
            }
        })
    
    # Task complexity analysis
    for category in goal_categories:
        complexity = random.randint(3, 15)
        metrics.append({
            "name": "agent_task_complexity",
            "value": complexity,
            "labels": {
                "goal_category": category,
                "metric_type": "task_complexity"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Conversation duration distribution
    metrics = []
    durations = [30, 60, 120, 180, 300, 600]
    for duration in durations:
        count = random.randint(5, 50) if duration < 300 else random.randint(1, 10)
        metrics.append({
            "name": "agent_conversation_duration_bucket",
            "value": count,
            "labels": {
                "le": str(duration),
                "metric_type": "duration_distribution"
            }
        })
    
    # User satisfaction metrics
    positive_feedback = random.randint(70, 95)
    negative_feedback = 100 - positive_feedback
    metrics.append({
        "name": "agent_feedback_positive",
        "value": positive_feedback,
        "labels": {"metric_type": "user_satisfaction"}
    })
    metrics.append({
        "name": "agent_feedback_negative",
        "value": negative_feedback,
        "labels": {"metric_type": "user_satisfaction"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Conversation volume trend
    metrics = []
    for day in range(30):
        day_count = random.randint(100, 500)
        day_timestamp = now - (day * 86400)
        day_str = datetime.datetime.fromtimestamp(day_timestamp).strftime("%Y-%m-%d")
        
        metrics.append({
            "name": "agent_conversations_daily",
            "value": day_count,
            "labels": {"day": day_str, "metric_type": "volume_trend"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Top Kubernetes operations
    metrics = []
    for tool in k8s_tools:
        count = random.randint(10, 200)
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": count,
            "labels": {"tool_name": tool, "metric_type": "top_operations"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Conversation flow effectiveness
    metrics = []
    for category in goal_categories:
        success_rate = random.uniform(0.7, 0.98)
        duration = random.uniform(60, 300)
        
        success_count = int(100 * success_rate)
        metrics.append({
            "name": "agent_tool_success_total",
            "value": success_count,
            "labels": {
                "task_id": "conversation_category",
                "goal_category": category,
                "metric_type": "flow_success"
            }
        })
        metrics.append({
            "name": "agent_task_execution_time_seconds",
            "value": duration,
            "labels": {
                "task_id": "total_conversation",
                "goal_category": category,
                "metric_type": "flow_duration"
            }
        })
        metrics.append({
            "name": "agent_conversation_effectiveness",
            "value": success_rate * 100,
            "labels": {
                "goal_category": category,
                "metric_type": "flow_effectiveness"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Conversation patterns by time
    metrics = []
    for hour in range(24):
        count = random.randint(10, 100)
        duration = random.uniform(60, 240)
        success_rate = random.uniform(0.8, 0.95)
        
        metrics.append({
            "name": "agent_conversation_patterns",
            "value": count,
            "labels": {
                "hour_of_day": str(hour),
                "metric_type": "hourly_count"
            }
        })
        metrics.append({
            "name": "agent_conversation_duration",
            "value": duration,
            "labels": {
                "hour_of_day": str(hour),
                "metric_type": "hourly_duration"
            }
        })
        metrics.append({
            "name": "agent_conversation_success_rate",
            "value": success_rate * 100,
            "labels": {
                "hour_of_day": str(hour),
                "metric_type": "hourly_success"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_reliability_error_metrics():
    """Generate reliability and error tracking metrics"""
    print("\nGenerating Reliability & Error Tracking metrics...")
    metrics = []
    
    # Overall system error rate
    total_calls = random.randint(1000, 5000)
    error_rate = random.uniform(0.02, 0.08)
    error_count = int(total_calls * error_rate)
    
    metrics.append({
        "name": "agent_tool_calls_total",
        "value": total_calls,
        "labels": {"metric_type": "system_total_calls"}
    })
    metrics.append({
        "name": "agent_tool_failure_total",
        "value": error_count,
        "labels": {"metric_type": "system_error_count"}
    })
    metrics.append({
        "name": "agent_system_error_rate",
        "value": error_rate * 100,
        "labels": {"metric_type": "overall_error_rate"}
    })
    
    # Error rate by component
    for tool in k8s_tools:
        component_calls = random.randint(100, 500)
        tool_error_rate = random.uniform(0.01, 0.1)
        component_failures = int(component_calls * tool_error_rate)
        
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": component_calls,
            "labels": {"tool_name": tool, "metric_type": "component_calls"}
        })
        metrics.append({
            "name": "agent_tool_failure_total",
            "value": component_failures,
            "labels": {"tool_name": tool, "metric_type": "component_failures"}
        })
        metrics.append({
            "name": "agent_component_error_rate",
            "value": tool_error_rate * 100,
            "labels": {"tool_name": tool, "metric_type": "component_error_rate"}
        })
    
    # MTTR (Mean Time To Recovery)
    recovery_times = []
    for i in range(20):
        recovery_time = random.uniform(30, 360)
        recovery_times.append(recovery_time)
        metrics.append({
            "name": "agent_recovery_time_seconds",
            "value": recovery_time,
            "labels": {"task_id": f"task_retry_{i}", "metric_type": "recovery_time"}
        })
    
    avg_recovery_time = sum(recovery_times) / len(recovery_times) if recovery_times else 0
    metrics.append({
        "name": "agent_mttr_seconds",
        "value": avg_recovery_time,
        "labels": {"metric_type": "mttr"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Error rate trend
    metrics = []
    now = int(time.time())
    for hour in range(24):
        hourly_error_rate = random.uniform(0.01, 0.08)
        hourly_calls = random.randint(50, 200)
        hourly_failures = int(hourly_calls * hourly_error_rate)
        
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": hourly_calls,
            "labels": {"hour": str(hour), "metric_type": "hourly_calls"}
        })
        metrics.append({
            "name": "agent_tool_failure_total",
            "value": hourly_failures,
            "labels": {"hour": str(hour), "metric_type": "hourly_failures"}
        })
        metrics.append({
            "name": "agent_hourly_error_rate",
            "value": hourly_error_rate * 100,
            "labels": {"hour": str(hour), "metric_type": "hourly_error_rate"}
        })
    
    # Retry frequency
    for hour in range(24):
        retry_count = random.randint(0, 10)
        
        metrics.append({
            "name": "agent_retry_count",
            "value": retry_count,
            "labels": {"hour": str(hour), "metric_type": "hourly_retry"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Error-update correlation
    metrics = []
    for hour in range(24):
        error_rate = random.uniform(0.01, 0.1)
        update_event = 1 if random.random() < 0.2 else 0
        
        hourly_calls = random.randint(50, 200)
        hourly_failures = int(hourly_calls * error_rate)
        
        metrics.append({
            "name": "agent_error_update_correlation",
            "value": error_rate * 100,
            "labels": {
                "hour": str(hour),
                "update_deployed": str(update_event),
                "metric_type": "error_update_correlation"
            }
        })
    
    # Most retried tasks
    for i, tool in enumerate(k8s_tools):
        retry_count = random.randint(0, 10)
        metrics.append({
            "name": "agent_task_retries",
            "value": retry_count,
            "labels": {"task_id": f"task_{tool}", "metric_type": "retried_tasks"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # System stability trend
    metrics = []
    for hour in range(24):
        success_rate = random.uniform(0.85, 0.99)
        
        metrics.append({
            "name": "agent_system_stability",
            "value": success_rate * 100,
            "labels": {"hour": str(hour), "metric_type": "stability_trend"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_task_decomposition():
    """Generate task decomposition metrics"""
    print("\nGenerating Task Decomposition Analysis metrics...")
    metrics = []
    
    # Average tasks per goal
    avg_tasks_per_goal = random.uniform(5, 15)
    metrics.append({
        "name": "agent_avg_tasks_per_goal",
        "value": avg_tasks_per_goal,
        "labels": {"metric_type": "tasks_per_goal"}
    })
    
    # Process plans and tasks - keep it small to avoid duplicate metrics
    plans = {}
    for i in range(5):  # Only create 5 plans to avoid overwhelming the Pushgateway
        plan_id = f"plan_{i}"
        category = random.choice(goal_categories)
        task_count = random.randint(3, 15)
        plans[plan_id] = {"task_count": task_count, "category": category}
        
        metrics.append({
            "name": "agent_plan_task_count",
            "value": task_count,
            "labels": {
                "plan_id": plan_id,
                "goal_category": category,
                "metric_type": "plan_tasks"
            }
        })
    
    # Average decomposition time
    decomp_times = []
    for i in range(10):  # Only 10 decomposition times to avoid duplicates
        decomp_time = random.uniform(2, 15)
        decomp_times.append(decomp_time)
        metrics.append({
            "name": "agent_decomposition_time",
            "value": decomp_time,
            "labels": {"decomp_id": f"decomp_{i}", "metric_type": "decomposition_time"}
        })
    
    avg_decomp_time = sum(decomp_times) / len(decomp_times) if decomp_times else 0
    metrics.append({
        "name": "agent_avg_decomposition_time",
        "value": avg_decomp_time,
        "labels": {"metric_type": "avg_decomp_time"}
    })
    
    # Fallback decomposition rate
    decomp_count = 30
    fallback_count = int(decomp_count * random.uniform(0.05, 0.2))
    metrics.append({
        "name": "agent_fallback_decomposition_count",
        "value": fallback_count,
        "labels": {"metric_type": "fallback_count"}
    })
    metrics.append({
        "name": "agent_decomposition_count",
        "value": decomp_count,
        "labels": {"metric_type": "total_decompositions"}
    })
    metrics.append({
        "name": "agent_fallback_decomposition_rate",
        "value": (fallback_count / decomp_count) * 100,
        "labels": {"metric_type": "fallback_rate"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Task distribution by plan
    metrics = []
    for plan_id, plan_data in plans.items():
        task_count = plan_data["task_count"]
        avg_exec_time = random.uniform(5, 20)
        
        metrics.append({
            "name": "agent_plan_task_count",
            "value": task_count,
            "labels": {"plan_id": plan_id, "metric_type": "plan_task_count"}
        })
        metrics.append({
            "name": "agent_plan_exec_time",
            "value": avg_exec_time,
            "labels": {"plan_id": plan_id, "metric_type": "plan_exec_time"}
        })
    
    # Decomposition time trend - use unique IDs to avoid duplicates
    now = int(time.time())
    for minute in range(20):  # Reduce to 20 samples to avoid flooding
        timestamp = now - (minute * 180)  # Space them out more
        decomp_time = random.uniform(2, 15)
        
        metrics.append({
            "name": "agent_decomposition_time_trend",
            "value": decomp_time,
            "labels": {
                "timestamp": str(timestamp),
                "sample_id": f"sample_{minute}",
                "metric_type": "time_trend"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Decomposition error patterns
    metrics = []
    for minute in range(15):  # Reduce to 15 samples
        timestamp = now - (minute * 240)  # Space them out even more
        error_count = random.randint(0, 3)
        fallback_count = random.randint(0, 2)
        
        metrics.append({
            "name": "agent_decomposition_errors",
            "value": error_count,
            "labels": {
                "timestamp": str(timestamp),
                "sample_id": f"error_sample_{minute}",
                "metric_type": "error_pattern"
            }
        })
        metrics.append({
            "name": "agent_decomposition_fallbacks",
            "value": fallback_count,
            "labels": {
                "timestamp": str(timestamp),
                "sample_id": f"fallback_sample_{minute}",
                "metric_type": "fallback_pattern"
            }
        })
    
    # Task execution time by priority
    for priority in priorities:
        exec_time = random.uniform(5, 30)
        task_count = random.randint(20, 100)
        
        metrics.append({
            "name": "agent_task_execution_time_by_priority",
            "value": exec_time,
            "labels": {
                "priority": priority,
                "metric_type": "execution_time_by_priority"
            }
        })
        metrics.append({
            "name": "agent_task_count_by_priority",
            "value": task_count,
            "labels": {
                "priority": priority,
                "metric_type": "task_count_by_priority"
            }
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Task complexity distribution
    metrics = []
    for tool in k8s_tools:
        complexity = random.uniform(5, 30)
        metrics.append({
            "name": "agent_task_complexity",
            "value": complexity,
            "labels": {
                "tool_name": tool,
                "metric_type": "task_complexity"
            }
        })
    
    # Optimal task count analysis
    optimal_count = random.randint(5, 15)
    metrics.append({
        "name": "agent_optimal_task_count",
        "value": optimal_count,
        "labels": {"metric_type": "optimal_count"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Token usage and cost by goal category
    metrics = []
    for category in goal_categories:
        token_usage = random.randint(500, 5000)
        cost = (token_usage / 1000) * random.uniform(0.002, 0.06)
        avg_tasks = random.randint(5, 15)
        
        metrics.append({
            "name": "agent_decomposition_token_usage",
            "value": token_usage,
            "labels": {
                "goal_category": category,
                "metric_type": "token_usage"
            }
        })
        metrics.append({
            "name": "agent_decomposition_cost_usd",
            "value": cost,
            "labels": {
                "goal_category": category,
                "metric_type": "decomposition_cost"
            }
        })
        metrics.append({
            "name": "agent_tasks_generated",
            "value": avg_tasks,
            "labels": {
                "goal_category": category,
                "metric_type": "avg_tasks_generated"
            }
        })
    
    # Decomposition quality score
    quality_score = random.uniform(60, 95)
    metrics.append({
        "name": "agent_decomposition_quality",
        "value": quality_score,
        "labels": {"metric_type": "quality_score"}
    })
    
    # Task dependency analysis
    dependency_success_rate = random.uniform(0.8, 0.95)
    overall_success_rate = random.uniform(0.85, 0.97)
    
    metrics.append({
        "name": "agent_dependency_success_rate",
        "value": dependency_success_rate * 100,
        "labels": {"metric_type": "dependency_success"}
    })
    metrics.append({
        "name": "agent_overall_success_rate",
        "value": overall_success_rate * 100,
        "labels": {"metric_type": "overall_success"}
    })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Decomposition feedback analysis
    metrics = []
    feedback_categories = [
        "decomposition_accuracy",
        "decomposition_completeness",
        "decomposition_efficiency",
        "decomposition_simplicity"
    ]
    
    for category in feedback_categories:
        total_feedback = random.randint(50, 200)
        positive_rate = random.uniform(0.7, 0.9)
        positive_count = int(total_feedback * positive_rate)
        
        metrics.append({
            "name": "agent_feedback_positive",
            "value": positive_count,
            "labels": {"feedback_category": category, "metric_type": "positive_feedback"}
        })
        metrics.append({
            "name": "agent_feedback_total",
            "value": total_feedback,
            "labels": {"feedback_category": category, "metric_type": "total_feedback"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def generate_tool_utilization():
    """Generate tool utilization metrics specifically for Kubernetes tools"""
    print("\nGenerating Tool Utilization metrics...")
    metrics = []
    
    # Top K8s tools by usage
    for i, tool in enumerate(k8s_tools):
        # Some tools are more popular than others
        if tool in ["kubectl_tool", "pod_tool", "deployment_tool"]:
            usage_multiplier = 2.0
        else:
            usage_multiplier = 1.0
            
        call_count = int(random.randint(20, 150) * usage_multiplier)
        success_count = int(call_count * random.uniform(0.85, 0.98))
        failure_count = call_count - success_count
        
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": call_count,
            "labels": {"tool_name": tool, "metric_id": f"usage_{i}", "metric_type": "tool_usage"}
        })
        metrics.append({
            "name": "agent_tool_success_total",
            "value": success_count,
            "labels": {"tool_name": tool, "metric_id": f"success_{i}", "metric_type": "tool_success"}
        })
        metrics.append({
            "name": "agent_tool_failure_total",
            "value": failure_count,
            "labels": {"tool_name": tool, "metric_id": f"failure_{i}", "metric_type": "tool_failure"}
        })
    
    # Tool success rates
    for i, tool in enumerate(k8s_tools):
        success_rate = random.uniform(0.7, 0.98)
        
        metrics.append({
            "name": "agent_tool_success_rate",
            "value": success_rate * 100,  # Convert to percentage
            "labels": {"tool_name": tool, "metric_id": f"rate_{i}", "metric_type": "success_rate"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Tool usage last 24 hours
    metrics = []
    now = int(time.time())
    for hour in range(24):
        hour_timestamp = now - (hour * 3600)
        
        # Only use a few tools to avoid too many metrics
        for i, tool in enumerate(k8s_tools[:5]):
            hour_of_day = datetime.datetime.fromtimestamp(hour_timestamp).hour
            # Business hours have more activity
            if 9 <= hour_of_day <= 17:
                rate_multiplier = 2.0
            else:
                rate_multiplier = 1.0
                
            hourly_calls = int(random.randint(1, 10) * rate_multiplier)
            
            metrics.append({
                "name": "agent_hourly_tool_usage",
                "value": hourly_calls,
                "labels": {
                    "tool_name": tool,
                    "hour": str(hour_of_day),
                    "metric_id": f"hourly_{hour}_{i}",
                    "metric_type": "hourly_usage"
                }
            })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Most error-prone tools
    metrics = []
    for i, tool in enumerate(k8s_tools):
        # Some tools are more error-prone
        if tool in ["security_tool", "node_tool"]:
            error_rate = random.uniform(0.05, 0.2)
        else:
            error_rate = random.uniform(0.01, 0.1)
            
        call_count = random.randint(20, 200)
        error_count = int(call_count * error_rate)
        
        metrics.append({
            "name": "agent_tool_error_count",
            "value": error_count,
            "labels": {"tool_name": tool, "metric_id": f"error_{i}", "metric_type": "error_count"}
        })
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": call_count,
            "labels": {"tool_name": tool, "metric_id": f"calls_{i}", "metric_type": "total_calls"}
        })
        metrics.append({
            "name": "agent_tool_error_rate",
            "value": error_rate * 100,  # Convert to percentage
            "labels": {"tool_name": tool, "metric_id": f"error_rate_{i}", "metric_type": "error_rate"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Tool usage patterns by time
    metrics = []
    for hour in range(24):
        hour_of_day = hour
        
        # Only use a few tools to avoid overwhelming the Pushgateway
        for i, tool in enumerate(k8s_tools[:3]):
            # Business hours have more activity
            if 9 <= hour_of_day <= 17:
                rate_multiplier = 2.0
            else:
                rate_multiplier = 1.0
                
            hourly_rate = random.uniform(0.01, 0.1) * rate_multiplier
            
            metrics.append({
                "name": "agent_tool_usage_pattern",
                "value": hourly_rate,
                "labels": {
                    "tool_name": tool,
                    "hour": str(hour_of_day),
                    "metric_id": f"pattern_{hour}_{i}",
                    "metric_type": "usage_pattern"
                }
            })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Tool popularity ranking
    metrics = []
    # Sort tools by a random popularity score
    popularity_scores = {tool: random.uniform(0.1, 1.0) for tool in k8s_tools}
    sorted_tools = sorted(popularity_scores.items(), key=lambda x: x[1], reverse=True)
    
    for rank, (tool, score) in enumerate(sorted_tools, 1):
        metrics.append({
            "name": "agent_tool_popularity",
            "value": score,
            "labels": {"tool_name": tool, "rank": str(rank), "metric_type": "popularity"}
        })
    
    # Unused tools - add a few simulated unused tools
    unused_tools = ["archived_kubectl_tool", "legacy_config_tool", "experimental_security_tool"]
    for i, tool in enumerate(unused_tools):
        metrics.append({
            "name": "agent_tool_calls_total",
            "value": 0,
            "labels": {"tool_name": tool, "metric_id": f"unused_{i}", "metric_type": "unused_tool"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)
    
    # Tool performance summary
    metrics = []
    for i, tool in enumerate(k8s_tools):
        total_uses = random.randint(50, 1000)
        success_rate = random.uniform(0.8, 0.99)
        success_count = int(total_uses * success_rate)
        avg_exec_time = random.uniform(0.2, 3.0)
        
        metrics.append({
            "name": "agent_tool_performance_uses",
            "value": total_uses,
            "labels": {"tool_name": tool, "metric_id": f"perf_uses_{i}", "metric_type": "performance_uses"}
        })
        metrics.append({
            "name": "agent_tool_performance_success",
            "value": success_count,
            "labels": {"tool_name": tool, "metric_id": f"perf_success_{i}", "metric_type": "performance_success"}
        })
        metrics.append({
            "name": "agent_tool_performance_time",
            "value": avg_exec_time,
            "labels": {"tool_name": tool, "metric_id": f"perf_time_{i}", "metric_type": "performance_time"}
        })
    
    # Push the batch of metrics
    push_metrics(metrics)

def run_k8s_simulators():
    """Run all Kubernetes metric simulators"""
    print("Starting Kubernetes metrics simulator...")
    
    # Delete any previous metrics with the same job name
    delete_previous_metrics()
    
    # Run all simulators
    generate_cost_management()
    generate_llm_operations()
    generate_operations_overview()
    generate_conversation_analytics()
    generate_reliability_error_metrics()
    generate_task_decomposition()
    generate_tool_utilization()
    
    print("\nAll Kubernetes metric simulators completed!")
    print("Metrics have been pushed to Prometheus Pushgateway at http://localhost:9091")
    print("Your Grafana dashboards should now display the simulated Kubernetes data.")

if __name__ == "__main__":
    run_k8s_simulators()