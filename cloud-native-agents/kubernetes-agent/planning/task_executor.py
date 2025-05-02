# planning/task_executor.py

import time
from typing import Optional
import yaml
import traceback
import datetime

from autogen import ConversableAgent

# Import monitoring components
from monitoring.agent_logger import get_logger
from monitoring.cost_tracker import get_cost_tracker
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger

class TaskExecutor:
    """Handles execution of individual planned tasks using agent + tools."""

    def __init__(self, config_path="configs/planning_config.yaml"):
        config = self._load_config(config_path)
        planner_config = config.get("planner", {})

        self.max_retries = planner_config.get("retry_attempts", 2)
        self.retry_delay = 2  # seconds (can also be made configurable)
        self.task_timeout_seconds = planner_config.get("task_timeout_seconds", 45)

        # Initialize monitoring tools
        self.logger = get_logger(__name__)
        self.cost_tracker = get_cost_tracker()
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        
        # Record initialization
        self.metrics.record_tool_call("task_executor_initialized")
        self.logger.info("TaskExecutor initialized successfully with max_retries=%d, timeout=%ds", 
                       self.max_retries, self.task_timeout_seconds)

    def _load_config(self, path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    async def execute_task(self, task: dict, agent: ConversableAgent, executor_agent: ConversableAgent, 
                         goal_category: str = "general", conversation_id: str = "unknown") -> dict:
        """
        Executes a single task with enhanced metrics collection.
        
        Args:
            task: The task to execute
            agent: The main conversable agent
            executor_agent: The executor agent
            goal_category: Category of the goal for metrics
            conversation_id: ID of the parent conversation
            
        Returns:
            dict: Result of task execution
        """

        try:
            task_id = task["id"]
            task_description = task["description"]
            plan_id = task.get("plan_id", "unknown")
            priority = task.get("priority", 0)
            
            # Get current hour for time-based metrics
            current_hour = datetime.datetime.now().hour
            hour_label = f"{current_hour:02d}:00"

            # Log task execution start with enhanced metadata
            self.logger.info("Starting execution of task: %s (id: %s, category: %s)", 
                           task_description, task_id, goal_category)
            
            # Create an audit entry for task execution with enhanced metadata
            self.audit.log_task_execution(
                plan_id=plan_id, 
                task_id=task_id, 
                task_text=task_description,
                goal_category=goal_category,
                priority=priority
            )
            
            # Set task metadata for enhanced metrics
            self.metrics.set_task_metadata(task_id, {
                "goal_category": goal_category,
                "conversation_id": conversation_id,
                "plan_id": plan_id,
                "priority": priority,
                "hour_of_day": hour_label,
                "description": task_description[:50]  # Truncate long descriptions
            })
            
            # Track execution time
            start_time = time.time()
            
            # Record tool call with detailed metadata
            self.metrics.record_tool_call(
                "task_execution", 
                task_id=task_id, 
                conversation_id=conversation_id
            )

            self.logger.info("Asking agent how to accomplish task: %s", task_description)
            
            # Create user prompt with task context
            user_prompt = f"User Goal: {task_description}\nSuggest safest available tool and parameters to achieve this."
            
            # Log the interaction with the agent
            self.logger.debug("Sending prompt to agent: %s", user_prompt)
            
            # Record LLM prompt metrics
            operation_type = "task_execution"
            model = "claude-3-5-sonnet-20241022"  # Use the actual model name from agent if available
            prompt_length = len(user_prompt)
            
            # Record prompt length
            if hasattr(self.metrics, 'record_prompt_length'):
                self.metrics.record_prompt_length(operation_type, prompt_length)
            
            # Record LLM call
            if hasattr(self.metrics, 'record_llm_call'):
                self.metrics.record_llm_call(
                    model=model,
                    temperature=0.3,  # Use actual temperature if available
                    operation_type=operation_type
                )
            
            try:
                # Use the direct method without awaiting
                llm_start_time = time.time()
                chat_result = executor_agent.initiate_chat(
                    recipient=agent,
                    message=user_prompt,
                    max_turns=2
                )
                llm_end_time = time.time()
                llm_latency = llm_end_time - llm_start_time
                
                # Record LLM latency
                if hasattr(self.metrics, 'record_llm_latency'):
                    self.metrics.record_llm_latency(model, llm_latency)
                
                # Record LLM success
                if hasattr(self.metrics, 'record_llm_result'):
                    self.metrics.record_llm_result(model, True, 0.3)  # Use actual temperature
                
                # Get agent's response from chat history
                messages = chat_result.chat_history
                if not messages:
                    error_msg = "No response received from agent."
                    self.logger.error(error_msg)
                    
                    # Record failure with detailed metadata
                    self.metrics.record_tool_result(
                        "agent_response", 
                        False,
                        goal_category=goal_category
                    )
                    
                    # Log audit failure with details
                    self.audit.log_event("task_failed", {
                        "task_id": task_id,
                        "error": error_msg,
                        "goal_category": goal_category,
                        "hour_of_day": hour_label,
                        "conversation_id": conversation_id
                    })
                    return {
                        "task_id": task_id,
                        "description": task_description,
                        "success": False,
                        "error": error_msg,
                        "goal_category": goal_category
                    }
                    
                agent_task_response = messages[-1]["content"]
                response_length = len(agent_task_response)
                self.logger.debug("Agent response: %s", agent_task_response)
                
                # Record response length
                if hasattr(self.metrics, 'record_response_length'):
                    self.metrics.record_response_length(operation_type, response_length)
                
                # Estimate token usage for the agent interaction
                prompt_tokens = int(len(user_prompt.split()) * 1.3)  # rough approximation
                response_tokens = int(len(agent_task_response.split()) * 1.3)  # rough approximation
                total_tokens = prompt_tokens + response_tokens
                
                # Track token details
                if hasattr(self.metrics, 'record_token_details'):
                    self.metrics.record_token_details(
                        task_id=task_id,
                        input_tokens=prompt_tokens,
                        output_tokens=response_tokens,
                        model=model,
                        operation_type=operation_type
                    )
                else:
                    # Fallback to basic token tracking
                    self.metrics.record_llm_tokens(task_id, total_tokens)
                
                # Track LLM token usage and cost with enhanced metadata
                self.cost_tracker.record_cost(
                    task_id=task_id,
                    model=model,
                    input_tokens=prompt_tokens,
                    output_tokens=response_tokens,
                    operation_type=operation_type,
                    goal_category=goal_category
                )
                
                # Record successful agent response
                self.metrics.record_tool_result(
                    "agent_response", 
                    True,
                    goal_category=goal_category
                )
                
                # Log LLM interaction in audit log
                if hasattr(self.audit, 'log_llm_interaction'):
                    self.audit.log_llm_interaction(
                        task_id=task_id,
                        model=model,
                        input_tokens=prompt_tokens,
                        output_tokens=response_tokens,
                        latency=llm_latency,
                        success=True,
                        operation_type=operation_type,
                        temperature=0.3  # Use actual temperature if available
                    )
                
                # Calculate execution duration
                end_time = time.time()
                execution_duration = end_time - start_time
                self.metrics.record_task_duration(
                    task_id, 
                    start_time, 
                    end_time,
                    goal_category=goal_category
                )
                
                # Log success event with comprehensive details
                self.audit.log_event("task_completed", {
                    "task_id": task_id,
                    "description": task_description,
                    "execution_time": round(execution_duration, 3),
                    "token_count": total_tokens,
                    "cost": self.cost_tracker.get_task_cost(task_id),
                    "goal_category": goal_category,
                    "hour_of_day": hour_label,
                    "conversation_id": conversation_id
                })
                
                # Log completion with performance metrics
                self.logger.info("Successfully executed task: %s (id: %s) in %.2f seconds", 
                               task_description, task_id, execution_duration)
                
                return {
                    "task_id": task_id,
                    "description": task_description,
                    "success": True,
                    "result": agent_task_response,
                    "execution_time": execution_duration,
                    "token_count": total_tokens,
                    "goal_category": goal_category
                }
                
            except Exception as e:
                # Record LLM failure
                if hasattr(self.metrics, 'record_llm_result'):
                    self.metrics.record_llm_result(model, False, 0.3)
                
                # Re-raise to be handled by the outer try-except
                raise

        except Exception as e:
            error_type = type(e).__name__
            self.logger.error("Error executing task %s: %s (%s)", 
                            task.get("id", "unknown"), str(e), error_type)
            traceback.print_exc()
            
            # Record failure metric with categorization
            self.metrics.record_tool_result(
                "task_execution", 
                False,
                goal_category=goal_category
            )
            
            # Log failure event with enhanced details
            self.audit.log_event("task_error", {
                "task_id": task.get("id", "unknown"),
                "error": str(e),
                "error_type": error_type,
                "traceback": traceback.format_exc(),
                "goal_category": goal_category,
                "conversation_id": conversation_id,
                "hour_of_day": hour_label
            })
            
            # Calculate execution time for failed task
            end_time = time.time()
            if 'start_time' in locals():
                execution_duration = end_time - start_time
                self.metrics.record_task_duration(
                    f"failed_{task.get('id', 'unknown')}", 
                    start_time, 
                    end_time,
                    goal_category=goal_category
                )
            
            return {
                "success": False,
                "task_id": task.get("id"),
                "description": task.get("description"),
                "error": str(e),
                "error_type": error_type,
                "goal_category": goal_category
            }
        
# Singleton instance
_task_executor: Optional[TaskExecutor] = None

def get_task_executor(config_path: str) -> TaskExecutor:
    global _task_executor
    if _task_executor is None:
        if config_path is None:
            _task_executor = TaskExecutor()
        else:
            _task_executor = TaskExecutor(config_path=config_path)
    return _task_executor