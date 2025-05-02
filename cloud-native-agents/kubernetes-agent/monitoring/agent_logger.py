# monitoring/agent_logger.py
"""
Rotating file logs: logs/agent.log
Usage Patterns

from monitoring.agent_logger import get_logger

log = get_logger()

log.info("Plan started with %d tasks", len(plan["tasks"]))
log.debug("Tool response: %s", tool_result)
log.warning("Retry triggered for task %s", task_id)
log.error("Failed to execute %s due to %s", tool_name, error)

"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

LOG_FORMAT = (
    "[%(asctime)s] [%(levelname)s] [%(module)s.%(funcName)s] "
    "%(message)s"
)

LOG_DIR = "logs"
LOG_FILE = "agent.log"
LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()


def setup_logger(name: str = "kube_assist") -> logging.Logger:
    """Sets up a rotating file + console logger."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if not logger.handlers:
        formatter = logging.Formatter(LOG_FORMAT)

        # File handler
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, LOG_FILE),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3
        )
        file_handler.setFormatter(formatter)

        # Console handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


# Global logger
agent_logger: Optional[logging.Logger] = None


def get_logger(name: str = "kube_assist") -> logging.Logger:
    """Returns the global logger (lazy initialized)."""
    global agent_logger
    if agent_logger is None:
        agent_logger = setup_logger(name)
    return agent_logger
