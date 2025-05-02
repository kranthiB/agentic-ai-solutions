# kubernetes_agent/feedback_learning/feedback_collector.py

import yaml
from feedback_learning.feedback_types import FeedbackType, FeedbackResult

class FeedbackCollector:
    """Collects feedback from user after task execution."""

    def __init__(self, config_path="configs/feedback_config.yaml"):
        with open(config_path, "r") as f:
            feedback_config = yaml.safe_load(f)

        self.enable_feedback = feedback_config["feedback"].get("enable_feedback", True)
        self.collection_mode = feedback_config["feedback"].get("feedback_collection_mode", "thumbs").lower()
        self.feedback_question = feedback_config["feedback"].get("feedback_question", "Was the action successful and helpful?")
        self.retry_limit = feedback_config["feedback"].get("retry_on_no_response", 2)

    async def collect_feedback(self, plan_id: str, task_id: str, task_description: str) -> dict:
        """
        Collects user feedback interactively.

        Args:
            plan_id (str): Plan ID.
            task_id (str): Task ID.
            task_description (str): What task was executed.

        Returns:
            dict: feedback dictionary ready to be stored
        """
        if not self.enable_feedback:
            return {}

        feedback_result = FeedbackResult.UNKNOWN
        free_text_feedback = None

        prompt = f"\n📝 Feedback Request for Task:\n- {task_description}\n{self.feedback_question}\n"

        for attempt in range(1, self.retry_limit + 2):
            try:
                if self.collection_mode == FeedbackType.THUMBS.value:
                    user_input = input(prompt + " (Enter 'y' for 👍 / 'n' for 👎): ").strip().lower()
                    if user_input == 'y':
                        feedback_result = FeedbackResult.POSITIVE
                        break
                    elif user_input == 'n':
                        feedback_result = FeedbackResult.NEGATIVE
                        break
                elif self.collection_mode == FeedbackType.STARS.value:
                    user_input = input(prompt + " (Enter rating 1-5): ").strip()
                    if user_input.isdigit() and 1 <= int(user_input) <= 5:
                        rating = int(user_input)
                        if rating >= 4:
                            feedback_result = FeedbackResult.POSITIVE
                        elif rating <= 2:
                            feedback_result = FeedbackResult.NEGATIVE
                        else:
                            feedback_result = FeedbackResult.NEUTRAL
                        break
                elif self.collection_mode == FeedbackType.FREE_TEXT.value:
                    user_input = input(prompt + " (Write your feedback text): ").strip()
                    if user_input:
                        free_text_feedback = user_input
                        feedback_result = FeedbackResult.POSITIVE if len(user_input) > 5 else FeedbackResult.NEUTRAL
                        break
                else:
                    raise ValueError(f"Unsupported feedback collection mode: {self.collection_mode}")
            except Exception as e:
                print(f"⚠️ Feedback collection error: {e}")

            print("❗ Invalid input. Please try again.")

        return {
            "plan_id": plan_id,
            "task_id": task_id,
            "task_description": task_description,
            "feedback_result": feedback_result.value,
            "free_text_feedback": free_text_feedback
        }
