# kubernetes_agent/planning/plan_improver.py

from typing import Dict, Optional
from memory.long_term_memory import get_long_term_memory
from monitoring.agent_logger import get_logger

class PlanImprover:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.memory = get_long_term_memory()

    async def improve_plan(
        self,
        user_goal: str,
        plan: Dict,
        top_k: int = 5,
        min_score: float = 0.5,
        namespace: str = "reflections"
    ) -> Dict:
        """
        Improves the plan by finding past insights related to the user goal.

        Args:
            user_goal (str): Current session goal or intent
            plan (Dict): Original plan (with list of tasks)
            top_k (int): How many past reflections to consider
            min_score (float): Relevance threshold (cosine similarity)
            namespace (str): Qdrant namespace

        Returns:
            Dict: plan with 'insights_applied' and optional improvements
        """
        self.logger.info("🔍 Querying long-term memory to enhance current plan...")
        matches = await self.memory.memory_store.query(
            query_text=user_goal,
            top_k=top_k,
            min_score=min_score,
            namespace=namespace
        )

        applied_insights = []

        for match in matches:
            insight = match["text"]
            score = match["score"]
            if score >= min_score:
                applied_insights.append({"insight": insight, "score": score})

        if applied_insights:
            plan["insights_applied"] = applied_insights
            self.logger.info(f"🧠 {len(applied_insights)} insights added to plan from memory")

        return plan

# Singleton instance
_plan_improver: Optional[PlanImprover] = None

def get_plan_improver() -> PlanImprover:
    global _plan_improver
    if _plan_improver is None:
        _plan_improver = PlanImprover()
    return _plan_improver