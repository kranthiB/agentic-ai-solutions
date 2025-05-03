# kubernetes_agent/planning/planner.py

import datetime
import time
from typing import Optional
import uuid
import yaml
from planning.task_decomposer import get_task_decomposer
from reflection.plan_improver import get_plan_improver
from monitoring.agent_logger import get_logger
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger

# Import guardrail service
from services.guardrail.guardrail_service import get_guardrail_service

class Planner:
    """Planner that takes a user goal, decomposes it into tasks, and generates a structured plan."""

    def __init__(self, config_path="configs/planning_config.yaml"):
        with open(config_path, "r") as f:
            planning_config = yaml.safe_load(f)

        self.default_priority_gap = planning_config["planner"].get(
            "default_priority_gap", 1
        )
        self.decomposer = get_task_decomposer(config_path=config_path)
        self.improver = get_plan_improver()  # 🧠 Plan improver initialized
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()

        # Initialize guardrail service
        self.guardrail_service = get_guardrail_service()

        self.logger.info(
            "Planner initialized with priority gap: %s", self.default_priority_gap
        )
        self.metrics.record_tool_call("planner_initialized")

    async def create_plan(self, user_goal: str, goal_category: str = "general") -> dict:
        self.logger.info(
            "Creating plan for user goal: %s (category: %s)", user_goal, goal_category
        )
        self.metrics.record_tool_call("plan_creation_attempt", task_id="planner")
        start_time = time.time()

        plan_id = str(uuid.uuid4())
        current_hour = datetime.datetime.now().hour
        hour_label = f"{current_hour:02d}:00"

        self.metrics.set_task_metadata(
            plan_id,
            {
                "goal_category": goal_category,
                "hour_of_day": hour_label,
                "operation_type": "planning",
            },
        )

        # Validate user goal through guardrails
        is_valid, reason = await self.guardrail_service.validate_user_input(
            user_input=user_goal,
            user_id="system",
            conversation_id=plan_id,
            metadata={"operation": "plan_creation", "goal_category": goal_category}
        )
        
        # Check if goal was blocked by guardrails
        if not is_valid:
            # Check enforcement level
            config = self.guardrail_service.config
            if config.get("enforcement_level") == "block":
                self.logger.warning(f"Goal creation blocked by guardrails: {reason}")
                self.audit.log_event("guardrail_blocked_goal", {
                    "plan_id": plan_id,
                    "goal": user_goal,
                    "reason": reason,
                    "goal_category": goal_category
                })
                
                # Return a minimal plan with an error message
                error_plan = {
                    "plan_id": plan_id,
                    "user_goal": user_goal,
                    "tasks": [{
                        "id": str(uuid.uuid4()),
                        "description": f"⚠️ This plan was blocked by safety guardrails: {reason}",
                        "priority": 1,
                        "status": "BLOCKED",
                        "error": reason
                    }],
                    "goal_category": goal_category,
                    "creation_time": time.time(),
                    "hour_of_day": hour_label,
                    "task_count": 1,
                    "status": "blocked_by_guardrails"
                }
                return error_plan
            else:
                # Log warning but continue with plan creation
                self.logger.warning(f"Guardrail warning for goal (non-blocking): {reason}")

        try:
            tasks = await self.decomposer.decompose(plan_id, user_goal, goal_category)

            # Validate each task through guardrails
            valid_tasks = []
            for task in tasks:
                task_description = task.get("description", "")
                
                # Validate task through guardrails
                is_valid, reason = await self.guardrail_service.validate_user_input(
                    user_input=task_description,
                    user_id="system",
                    conversation_id=plan_id,
                    metadata={"task_id": task.get("id"), "operation": "task_creation"}
                )
                
                # Check if task was blocked by guardrails
                if not is_valid:
                    # Check enforcement level
                    config = self.guardrail_service.config
                    if config.get("enforcement_level") == "block":
                        self.logger.warning(f"Task creation blocked by guardrails: {reason}")
                        self.audit.log_event("guardrail_blocked_task", {
                            "plan_id": plan_id,
                            "task_id": task.get("id"),
                            "task": task_description,
                            "reason": reason
                        })
                        
                        # Replace task with a warning task
                        task["description"] = f"⚠️ Task blocked by safety guardrails: {reason}"
                        task["status"] = "BLOCKED"
                        task["error"] = reason
                    else:
                        # Log warning but keep task
                        self.logger.warning(f"Guardrail warning for task (non-blocking): {reason}")
                
                # Add task to list (potentially modified)
                valid_tasks.append(task)
            
            # Use filtered tasks list
            tasks = valid_tasks

            for idx, task in enumerate(tasks):
                priority = task.get("priority", (idx + 1) * self.default_priority_gap)
                task["priority"] = priority
                self.metrics.set_task_metadata(
                    task["id"],
                    {
                        "plan_id": plan_id,
                        "goal_category": goal_category,
                        "priority": priority,
                        "task_position": idx + 1,
                        "total_tasks": len(tasks),
                        "hour_of_day": hour_label,
                    },
                )

            sorted_tasks = sorted(tasks, key=lambda x: x["priority"])

            plan = {
                "plan_id": plan_id,
                "user_goal": user_goal,
                "tasks": sorted_tasks,
                "goal_category": goal_category,
                "creation_time": time.time(),
                "hour_of_day": hour_label,
                "task_count": len(sorted_tasks),
            }

            # 🧠 Enhance plan with prior insights
            improved_plan = await self.improver.improve_plan(
                user_goal=user_goal, plan=plan, top_k=5
            )

            if "insights_applied" in improved_plan:
                self.logger.info(
                    "🧠 Applied %d prior insights to the plan",
                    len(improved_plan["insights_applied"]),
                )

            self.metrics.record_tool_result("plan_creation", True, goal_category)

            if hasattr(self.metrics, "record_gauge"):
                self.metrics.record_gauge(
                    "plan_task_count",
                    len(sorted_tasks),
                    {"goal_category": goal_category},
                )

            end_time = time.time()
            self.metrics.record_task_duration(
                "plan_creation", start_time, end_time, goal_category
            )

            self.audit.log_plan_created(plan_id, user_goal, len(tasks), goal_category)

            self.logger.info(
                "Plan created with ID: %s, containing %d tasks (category: %s)",
                plan_id,
                len(tasks),
                goal_category,
            )

            return improved_plan

        except Exception as e:
            error_type = type(e).__name__
            self.metrics.record_tool_result("plan_creation", False, goal_category)

            self.logger.error("Plan creation failed: %s (%s)", str(e), error_type)

            self.audit.log_event(
                "plan_creation_failed",
                {
                    "plan_id": plan_id,
                    "user_goal": user_goal,
                    "goal_category": goal_category,
                    "error": str(e),
                    "error_type": error_type,
                },
            )

            end_time = time.time()
            self.metrics.record_task_duration(
                "failed_plan_creation", start_time, end_time, goal_category
            )
            raise

# Singleton instance
_planner: Optional[Planner] = None

def get_planner() -> Planner:
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner
