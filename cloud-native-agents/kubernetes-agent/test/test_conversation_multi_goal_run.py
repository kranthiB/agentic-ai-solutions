# test_conversation_multi_goal_run.py

import asyncio
from core.conversation_manager import ConversationManager

async def run_single_goal(user_goal: str, conversation_manager: ConversationManager):
    print(f"\n🚀 Starting Kubernetes Agent Conversation for Goal:\n➡️ '{user_goal}'\n")
    await conversation_manager.run_conversation(user_goal)
    print("\n✅ Goal completed successfully!\n" + "="*80)

async def main():
    # Initialize one Conversation Manager for session
    conversation_manager = ConversationManager()

    # List of multiple user goals to simulate
    user_goals = [
        "Scale nginx deployment to 5 replicas and restart the service",
        "Create a new namespace called 'test-env' and deploy a Redis instance",
        "Analyze node resource utilization for cluster optimization",
        "Fetch logs for a failed pod named 'api-backend' in 'production' namespace",
        "Create a ConfigMap for nginx custom configuration and update deployment",
    ]

    # Loop through each goal and execute sequentially
    for goal in user_goals:
        await run_single_goal(goal, conversation_manager)

if __name__ == "__main__":
    asyncio.run(main())
