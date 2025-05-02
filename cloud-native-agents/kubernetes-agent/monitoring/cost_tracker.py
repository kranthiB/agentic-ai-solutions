# monitoring/cost_tracker.py
from collections import defaultdict
from typing import Dict, Optional, Any

# Approximate cost per 1K tokens in USD (can be updated per model pricing)
MODEL_COST_TABLE = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
    "claude-3-7-sonnet-20250219": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "gemini-1.5-pro": {"input": 0.0025, "output": 0.005},
    "gemini-2.5-pro": {"input": 0.0030, "output": 0.006},  # Adjust if official rate changes
}

class CostTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cost_summary = defaultdict(lambda: defaultdict(float))  # task_id → model → cost breakdown
        self.metadata = defaultdict(dict)  # task_id → metadata

    def record_cost(
        self,
        task_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation_type: str = "unknown",
        goal_category: str = "unknown"
    ):
        model_key = model.lower()
        pricing = MODEL_COST_TABLE.get(model_key, {"input": 0.0, "output": 0.0})

        cost_in = (input_tokens / 1000.0) * pricing["input"]
        cost_out = (output_tokens / 1000.0) * pricing["output"]
        total = round(cost_in + cost_out, 6)

        self.cost_summary[task_id][model_key] += total
        
        # Store metadata for enhanced labeling
        if task_id not in self.metadata:
            self.metadata[task_id] = {}
        self.metadata[task_id]["operation_type"] = operation_type
        self.metadata[task_id]["goal_category"] = goal_category
        self.metadata[task_id]["input_tokens"] = input_tokens
        self.metadata[task_id]["output_tokens"] = output_tokens

    def get_task_cost(self, task_id: str) -> Dict[str, float]:
        return dict(self.cost_summary.get(task_id, {}))

    def get_total_cost(self) -> float:
        return round(sum(
            sum(model_costs.values()) for model_costs in self.cost_summary.values()
        ), 6)

    def get_breakdown(self) -> Dict[str, Dict[str, float]]:
        return {task: dict(models) for task, models in self.cost_summary.items()}
        
    def get_metadata(self, task_id: str) -> Dict[str, Any]:
        """Get metadata associated with a task_id"""
        return self.metadata.get(task_id, {})


# Singleton instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker