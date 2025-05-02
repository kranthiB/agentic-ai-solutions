# kubernetes_agent/planning/planner.py

import datetime
import time
import uuid
import yaml
from planning.task_decomposer import TaskDecomposer
from reflection.plan_improver import PlanImprover
from monitoring.agent_logger import get_logger
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger


class Planner:
    """Planner that takes a user goal, decomposes it into tasks, and generates a structured plan."""

    def __init__(self, config_path="configs/planning_config.yaml"):
        with open(config_path, "r") as f:
            planning_config = yaml.safe_load(f)

        self.default_priority_gap = planning_config["planner"].get(
            "default_priority_gap", 1
        )
        self.decomposer = TaskDecomposer(config_path=config_path)
        self.improver = PlanImprover()  # 🧠 Plan improver initialized
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()

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

        try:
            tasks = await self.decomposer.decompose(plan_id, user_goal, goal_category)

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
