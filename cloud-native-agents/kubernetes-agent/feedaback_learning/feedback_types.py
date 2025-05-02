# kubernetes_agent/feedback_learning/feedback_types.py

from enum import Enum

class FeedbackType(Enum):
    """Types of feedback collection modes supported."""
    THUMBS = "thumbs"          # 👍👎
    STARS = "stars"            # ⭐⭐⭐⭐⭐
    FREE_TEXT = "free_text"     # User writes comments

class FeedbackResult(Enum):
    """Possible feedback outcomes."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"

class FeedbackStorage(Enum):
    """Where to persist feedback."""
    REDIS = "redis"
    QDRANT = "qdrant"
    BOTH = "both"

class FeedbackConstants:
    """Miscellaneous constants used for feedback."""
    DEFAULT_QUESTION = "Was the action successful and helpful?"
    DEFAULT_RETRY_LIMIT = 2
