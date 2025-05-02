# kubernetes_agent/feedback_learning/learning_manager.py
# await self.learning_manager.process_feedback(feedback)
import yaml
from feedback_learning.feedback_types import FeedbackResult
from memory.memory_store import get_memory_store
from datetime import datetime

class LearningManager:
    """Handles learning updates based on user feedback."""

    def __init__(self, config_path="configs/feedback_config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        feedback_config = config.get("feedback", {})
        self.auto_memory_update_on_positive = feedback_config.get("auto_memory_update_on_positive", True)
        self.auto_memory_update_on_negative = feedback_config.get("auto_memory_update_on_negative", False)

        # Memory store instance (Redis + Qdrant handled internally)
        self.memory_store = get_memory_store()

    async def process_feedback(self, feedback: dict):
        """
        Analyze feedback and trigger memory updates accordingly.

        Args:
            feedback (dict): Feedback dictionary.
        """
        feedback_result = feedback.get("feedback_result", FeedbackResult.UNKNOWN.value)

        if feedback_result == FeedbackResult.POSITIVE.value:
            if self.auto_memory_update_on_positive:
                await self.handle_positive_feedback(feedback)

        elif feedback_result == FeedbackResult.NEGATIVE.value:
            if self.auto_memory_update_on_negative:
                await self.handle_negative_feedback(feedback)

        else:
            print(f"⚪ Neutral/Unknown Feedback for task {feedback.get('task_id')}: No action taken.")

    async def handle_positive_feedback(self, feedback: dict):
        """
        Update memory to mark this task as a successful pattern.

        Args:
            feedback (dict): Feedback dictionary.
        """
        success_record = {
            "plan_id": feedback.get("plan_id"),
            "task_id": feedback.get("task_id"),
            "task_description": feedback.get("task_description"),
            "feedback_result": feedback.get("feedback_result"),
            "free_text_feedback": feedback.get("free_text_feedback", None),
            "timestamp": datetime.utcnow().isoformat(),
            "learning_tag": "successful_task"
        }

        # Store in long-term memory (Qdrant assumed internally)
        await self.memory_store.store_long_term_memory(
            content=success_record,
            namespace="successful_tasks"
        )

        print(f"✅ Positive feedback saved to memory: Task {feedback['task_id']} marked as success.")

    async def handle_negative_feedback(self, feedback: dict):
        """
        Update memory or logs to mark this task as a failed case needing improvement.

        Args:
            feedback (dict): Feedback dictionary.
        """
        failure_record = {
            "plan_id": feedback.get("plan_id"),
            "task_id": feedback.get("task_id"),
            "task_description": feedback.get("task_description"),
            "feedback_result": feedback.get("feedback_result"),
            "free_text_feedback": feedback.get("free_text_feedback", None),
            "timestamp": datetime.utcnow().isoformat(),
            "learning_tag": "failed_task"
        }

        # Store in long-term memory (Qdrant assumed internally)
        await self.memory_store.store_long_term_memory(
            content=failure_record,
            namespace="failed_tasks"
        )

        print(f"⚠️ Negative feedback saved to memory: Task {feedback['task_id']} marked for improvement.")
