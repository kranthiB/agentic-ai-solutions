# test_feedback_learning_run.py

import asyncio

from feedback_learning.feedback_collector import FeedbackCollector
from feedback_learning.feedback_store import FeedbackStore
from feedback_learning.learning_manager import LearningManager

async def main():
    # Instantiate modules
    feedback_collector = FeedbackCollector()
    feedback_store = FeedbackStore()
    learning_manager = LearningManager()

    # Simulate a dummy completed task
    plan_id = "plan-1234"
    task_id = "task-5678"
    task_description = "Scale nginx deployment to 5 replicas"

    print("\n🚀 Dummy Task Completed:", task_description)

    # Step 1: Collect feedback from user
    feedback = await feedback_collector.collect_feedback(plan_id, task_id, task_description)

    if feedback:
        print("\n📝 Feedback collected:")
        print(feedback)

        # Step 2: Store feedback in Redis and/or Qdrant
        feedback_store.save_feedback(feedback)
        print("\n💾 Feedback saved successfully.")

        # Step 3: Process feedback to update learning
        await learning_manager.process_feedback(feedback)
        print("\n🧠 Learning manager processed feedback successfully.")

    else:
        print("\n⚪ No feedback collected. Skipping storage and learning.")

if __name__ == "__main__":
    asyncio.run(main())
