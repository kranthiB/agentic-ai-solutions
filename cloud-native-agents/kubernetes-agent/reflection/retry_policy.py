# kubernetes_agent/reflection/retry_policy.py

from typing import Dict, Any
from monitoring.agent_logger import get_logger

logger = get_logger(__name__)


class RetryPolicy:
    def __init__(self, max_retries: int = 2, retryable_errors: list = None):
        self.max_retries = max_retries
        self.retryable_errors = retryable_errors or [
            "connection refused",
            "resource not found",
            "timeout",
            "temporary unavailable"
        ]

    def should_retry(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Determines whether a failed task should be retried.

        Args:
            task (Dict): Task dictionary with 'id', 'description', and optional 'retry_count'
            result (Dict): Task response/result containing 'error' key if failed

        Returns:
            bool: True if retry is allowed, False otherwise
        """
        task_id = task.get("id")
        retry_count = task.get("retry_count", 0)
        error_msg = result.get("error", "").lower()

        if retry_count >= self.max_retries:
            logger.warning(f"❌ Retry limit exceeded for task {task_id}")
            return False

        for keyword in self.retryable_errors:
            if keyword in error_msg:
                logger.info(f"🔁 Retry approved for task {task_id} (matched keyword: '{keyword}')")
                return True

        logger.info(f"🛑 Retry not allowed for task {task_id}: error not retryable")
        return False
