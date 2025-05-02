# kubernetes_agent/reflection/reflection_engine.py

import time
import uuid
from typing import List, Dict, Optional

from monitoring.agent_logger import get_logger
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger
from memory.long_term_memory import get_long_term_memory
from reflection.retry_policy import get_retry_policy
from planning.task_executor import get_task_executor  # <-- updated

class ReflectionEngine:
    def __init__(self, max_retries: int = 2):
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        self.long_term_memory = get_long_term_memory()
        self.retry_policy = get_retry_policy(max_retries=max_retries)
        self.task_executor = get_task_executor()  # <-- use your actual executor

    async def reflect_on_tasks(
        self,
        task_results: List[Dict],
        plan_id: str,
        session_id: str,
        goal: str,
        agent,
        executor_agent,
        goal_category: str = "general"
    ) -> Dict:
        reflection_id = str(uuid.uuid4())
        reflection_start = time.time()

        self.logger.info("🧠 Reflecting on %d tasks (plan_id=%s)", len(task_results), plan_id)
        self.metrics.record_tool_call("reflection_engine", task_id=reflection_id)

        insights = []
        retried = []

        for task in task_results:
            task_id = task.get("id")
            description = task.get("description", "")
            duration = task.get("duration", 0.0)
            success = task.get("status", False)
            result = task.get("response", {})
            retry_count = task.get("retry_count", 0)

            if success:
                insights.append(f"✅ Task succeeded: {description} (duration: {duration:.2f}s)")
                continue

            error_msg = result.get("error", "Unknown error")
            insights.append(f"❌ Task failed: {description}\n ➤ Error: {error_msg}")

            if self.retry_policy.should_retry(task, result):
                try:
                    self.logger.info(f"🔁 Retrying task {task_id} (retry #{retry_count + 1})")
                    task["retry_count"] = retry_count + 1

                    retry_result = await self.task_executor.execute_task(
                        task=task,
                        agent=agent,
                        executor_agent=executor_agent,
                        goal_category=goal_category,
                        conversation_id=session_id
                    )

                    if retry_result.get("success"):
                        insights.append(f"✅ Retry succeeded for task {task_id}")
                        retried.append(task_id)
                    else:
                        insights.append(f"❌ Retry failed for task {task_id}: {retry_result.get('error', 'unknown error')}")

                except Exception as e:
                    self.logger.error(f"⚠️ Retry crash for task {task_id}: {e}")
                    insights.append(f"💥 Retry error for task {task_id}: {str(e)}")

        reflection_end = time.time()
        summary = {
            "reflection_id": reflection_id,
            "plan_id": plan_id,
            "session_id": session_id,
            "goal": goal,
            "timestamp": time.time(),
            "goal_category": goal_category,
            "total_tasks": len(task_results),
            "retried_tasks": retried,
            "insights": insights,
        }

        self.metrics.record_task_duration("task_reflection", reflection_start, reflection_end, goal_category)
        self.audit.log_event("task_reflection", summary)

        for insight_text in insights:
            await self.long_term_memory.memory_store.store_long_term_memory(
                content={
                    "text": insight_text,
                    "plan_id": plan_id,
                    "session_id": session_id,
                    "goal": goal,
                    "category": goal_category,
                    "type": "reflection_insight"
                },
                namespace="reflections"
            )

        return summary

# Singleton instance
_reflection_engine: Optional[ReflectionEngine] = None

def get_reflection_engine() -> ReflectionEngine:
    global _reflection_engine
    if _reflection_engine is None:
        _reflection_engine = ReflectionEngine()
    return _reflection_engine