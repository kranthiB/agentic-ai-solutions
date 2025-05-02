# kubernetes_agent/planning/task_decomposer.py

import time
import uuid
import yaml
import asyncio
from typing import List, Dict, Optional

from autogen import AssistantAgent, LLMConfig 
from utils.prompt_templates import TASK_DECOMPOSITION_INSTRUCTION , TASK_DECOMPOSER_SYSTEM_PROMPT

from monitoring.agent_logger import get_logger
from monitoring.cost_tracker import get_cost_tracker
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger



class TaskDecomposer:
    """LLM-powered Task Decomposer specialized for Kubernetes goals."""

    def __init__(self, config_path: str = "configs/planning_config.yaml"):
        with open(config_path, "r") as f:
            planning_config = yaml.safe_load(f)

        self.planning_max_steps = planning_config["planner"].get("planning_max_steps", 10)
        self.default_model = planning_config["planner"].get("default_model", "claude-3-5-sonnet-20241022") #claude-3-7-sonnet-20250219")
        self.temperature = planning_config["planner"].get("temperature", 0.3)
        self.max_tokens = planning_config["planner"].get("max_tokens", 2048)
        self.timeout_seconds = planning_config["planner"].get("timeout_seconds", 30)
        self.api_key = planning_config["planner"].get("api_key")
        self.api_base = planning_config["planner"].get("api_base")
        self.provider = planning_config["planner"].get("provider", "anthropic")  # default to anthropic

        # Initialize monitoring tools
        self.logger = get_logger(__name__)
        self.cost_tracker = get_cost_tracker()
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()

        # Init the Assistant Agent (ag2)
        self.assistant = AssistantAgent(
            name="TaskDecomposerAgent",
            system_message=TASK_DECOMPOSER_SYSTEM_PROMPT,
            llm_config= LLMConfig( model=self.default_model, 
                                  api_type=self.provider,
                                  api_key=self.api_key,
                                  base_url=self.api_base),
        )
        # Initialize additional metrics
        self.metrics.record_tool_call("task_decomposer_initialized")
        self.logger.info("TaskDecomposer initialized with model: %s, provider: %s", 
                         self.default_model, self.provider)

    async def decompose(self, plan_id: str, user_goal: str, goal_category: str = "general") -> List[Dict]:
        """
        Decompose a high-level Kubernetes goal into minimal atomic tasks using an LLM.

        Args:
            user_goal (str): Kubernetes user goal description.

        Returns:
            List[Dict]: List of atomic task dictionaries with id, description, priority, and status.
        """
        filled_prompt = TASK_DECOMPOSITION_INSTRUCTION.format(user_goal=user_goal)
        task_id = str(uuid.uuid4())
        operation_type = "task_decomposition"

        # Record decomposition request in metrics
        self.metrics.record_tool_call("decomposition_attempt", task_id=task_id)
        
        # Record prompt length for prompt size analysis
        prompt_length = len(filled_prompt)
        self.metrics.record_prompt_length(operation_type, prompt_length)

        try:
            self.logger.info(f"Starting task decomposition for goal: {user_goal}")
            # Create audit entry for decomposition start with categorization
            self.audit.log_event("decomposition_started", {
                "task_id": task_id,
                "user_goal": user_goal,
                "goal_category": goal_category,
                "plan_id": plan_id,
            })

            # Track execution time
            start_time = time.time()
            self.metrics.set_task_metadata(task_id, {
                "operation_type": operation_type,
                "goal_category": goal_category,
                "prompt_length": prompt_length
            })
            
            # Record LLM call with more metadata
            self.metrics.record_llm_call(
                model=self.default_model,
                temperature=self.temperature,
                operation_type=operation_type
            )
            try:
                # Attempt LLM call with timeout monitoring
                response = await asyncio.wait_for(
                    self.assistant.a_generate_reply(
                        sender=None, 
                        messages=[{
                            "role": "user",
                            "content": filled_prompt
                        }],
                    ),
                    timeout=self.timeout_seconds
            )
            except asyncio.TimeoutError:
                # Record specific timeout metric
                self.metrics.record_llm_timeout(self.default_model)
                raise

            # Calculate LLM latency
            llm_latency = time.time() - start_time
            self.metrics.record_llm_latency(self.default_model, llm_latency)

            # Estimate token usage with more detailed breakdowns
            input_tokens = int(len(filled_prompt.split()) * 1.3)  # rough approximation

            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)

            output_tokens = int(len(response_text.split()) * 1.3)  # rough approximation
            total_tokens = input_tokens + output_tokens
            # Record response length for analysis
            response_length = len(response_text)
            self.metrics.record_response_length(operation_type, response_length)

            # Track detailed token usage
            self.metrics.record_token_details(
                task_id=task_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.default_model,
                operation_type=operation_type
            )

            # Track LLM usage costs with enhanced categorization
            self.cost_tracker.record_cost(
                task_id=task_id,
                model=self.default_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation_type=operation_type,
                goal_category=goal_category
            )

            # Record basic token usage for backward compatibility
            self.metrics.record_llm_tokens(task_id, total_tokens, 
                                          model=self.default_model,
                                          operation_type=operation_type)

            # Record LLM result
            self.metrics.record_llm_result(self.default_model, True, self.temperature)
            
            # Log detailed LLM interaction in audit log
            self.audit.log_llm_interaction(
                task_id=task_id,
                model=self.default_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency=llm_latency,
                success=True,
                operation_type=operation_type,
                temperature=self.temperature
            )

            # Process the response into tasks
            subtasks = self._parse_tasks(response_text)
            tasks = self._create_task_objects(plan_id, subtasks, goal_category)

            # Record task creation success
            self.metrics.record_tool_result("task_decomposition", True, goal_category)
            
            # Record timing metrics with enhanced labeling
            end_time = time.time()
            self.metrics.record_task_duration(task_id, start_time, end_time, goal_category)
            
            # Log successful completion with task count
            self.logger.info("Successfully decomposed goal into %d tasks (task_id: %s)", 
                           len(tasks), task_id)
            
            # Log task breakdown for auditing with enhanced metadata
            for idx, task in enumerate(tasks):
                self.audit.log_event("task_defined", {
                    "parent_task_id": task_id,
                    "task_id": task["id"],
                    "description": task["description"],
                    "priority": task["priority"],
                    "goal_category": goal_category,
                    "task_position": idx + 1,
                    "total_tasks": len(tasks)
                })
                
                # Create task dependency metrics
                self.metrics.record_task_dependency(task_id)
                self.metrics.record_task_dependency(task_id, success=True)
                
            return tasks

        except asyncio.TimeoutError:
            self.logger.error("LLM Task Decomposition timed out.")
            
            # Log the timeout event with more details
            self.audit.log_event("decomposition_timeout", {
                "task_id": task_id,
                "timeout_seconds": self.timeout_seconds,
                "goal_category": goal_category,
                "prompt_length": prompt_length
            })
            
            # Record failure metrics with more detail
            self.metrics.record_tool_result("task_decomposition", False, goal_category)
            self.metrics.record_llm_result(self.default_model, False, self.temperature)
            
            # Use fallback with instrumentation
            return self._fallback_decomposition(user_goal, goal_category)

        except Exception as e:
            error_type = type(e).__name__
            self.logger.error(f"LLM Task Decomposition failed: {str(e)}")
            
            # Log detailed error event
            self.audit.log_event("decomposition_error", {
                "task_id": task_id,
                "error": str(e),
                "error_type": error_type,
                "goal_category": goal_category,
                "prompt_length": prompt_length
            })
            
            # Record failure metrics with error categorization
            self.metrics.record_tool_result("task_decomposition", False, goal_category)
            self.metrics.record_llm_result(self.default_model, False, self.temperature)
            
            # Track in cost metrics that we attempted but failed
            end_time = time.time()
            self.metrics.record_task_duration(f"failed_{task_id}", start_time, end_time, goal_category)
            
            # Use fallback with instrumentation
            return self._fallback_decomposition(plan_id, user_goal, goal_category)

    def _parse_tasks(self, llm_output: str) -> List[str]:
        """Parse LLM output into a list of clean task descriptions."""
        lines = llm_output.strip().split("\n")
        subtasks = []

        for line in lines:
            line = line.strip().lstrip("-").lstrip("*").strip()
            if line:
                subtasks.append(line)

        return subtasks[:self.planning_max_steps]

    def _create_task_objects(self, plan_id: str, subtasks: List[str], goal_category: str = "general") -> List[Dict]:
        """Create structured task dictionaries with enhanced metadata."""
        tasks = []
        for idx, task_desc in enumerate(subtasks):
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "description": task_desc,
                "priority": idx + 1,
                "status": "PENDING",
                "goal_category": goal_category,  # Add category for metrics grouping
                "plan_id": plan_id,  # Add plan_id to each task
                "creation_time": time.time()     # Add timestamp for latency tracking
            }
            tasks.append(task)
            
            # Set task metadata for metrics enhancement
            self.metrics.set_task_metadata(task_id, {
                "goal_category": goal_category,
                "priority": idx + 1,
                "task_number": idx + 1,
                "total_tasks": len(subtasks),
                "plan_id": plan_id,
            })
            
        return tasks

    def _fallback_decomposition(self, plan_id: str, user_goal: str, goal_category: str = "general") -> List[Dict]:
        """Simple fallback decomposition with enhanced instrumentation."""
        self.logger.warning("Using fallback decomposition (string split).")
        
        # Track fallback usage with goal category
        self.metrics.record_tool_call("fallback_decomposition")
        
        start_time = time.time()
        subtasks = user_goal.split(" and ")

        tasks = []
        for idx, subgoal in enumerate(subtasks):
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "description": subgoal.strip(),
                "priority": idx + 1,
                "status": "PENDING",
                "goal_category": goal_category,
                "plan_id": plan_id,
                "fallback_created": True        # Mark as fallback for analysis
            }
            tasks.append(task)
            
            # Set task metadata
            self.metrics.set_task_metadata(task_id, {
                "goal_category": goal_category,
                "fallback": True,
                "priority": idx + 1,
                "plan_id": plan_id
            })
            
            # Log fallback task creation with more metadata
            self.audit.log_event("fallback_task_created", {
                "task_id": task_id,
                "description": subgoal.strip(),
                "priority": idx + 1,
                "goal_category": goal_category,
                "task_position": idx + 1,
                "plan_id": plan_id,
                "total_tasks": len(subtasks)
            })
            
        # Record timing for fallback execution
        end_time = time.time()
        self.metrics.record_task_duration("fallback_decomposition", start_time, end_time, goal_category)
        
        # Record success metric for fallback with goal category
        self.metrics.record_tool_result("fallback_decomposition", True, goal_category)

        return tasks


# Singleton instance
_task_decomposer: Optional[TaskDecomposer] = None

def get_task_decomposer(config_path: str) -> TaskDecomposer:
    global _task_decomposer
    if _task_decomposer is None:
        if config_path is None:
            _task_decomposer = TaskDecomposer()
        else:
            _task_decomposer = TaskDecomposer(config_path=config_path)
    return _task_decomposer