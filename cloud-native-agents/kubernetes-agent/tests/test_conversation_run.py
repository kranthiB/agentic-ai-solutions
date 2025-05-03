"""
🚀 Starting Kubernetes Agent Conversation...

🤖 Understanding user goal:
'Scale nginx deployment to 5 replicas and then restart the service'

📝 Plan created with 2 tasks (Plan ID: 123e4567-e89b-12d3-a456-426614174000)
    1. Scale nginx deployment to 5 replicas
    2. Restart the service

🚀 Executing tasks...

🔎 Asking agent: How to accomplish -> Scale nginx deployment to 5 replicas
🛠️ Agent Response:
Use tool `scale_deployment` with parameters deployment_name=nginx, replicas=5.

✅ Tool 'scale_deployment' executed successfully.

📝 Feedback Request for Task:
- Scale nginx deployment to 5 replicas
Was the action successful and helpful?
 (Enter 'y' for 👍 / 'n' for 👎): y

💾 Feedback saved successfully.
✅ Positive feedback saved to memory: Task abc123 marked as success.

🔎 Asking agent: How to accomplish -> Restart the service
🛠️ Agent Response:
Use tool `restart_deployment` with parameters deployment_name=nginx.

✅ Tool 'restart_deployment' executed successfully.

📝 Feedback Request for Task:
- Restart the service
Was the action successful and helpful?
 (Enter 'y' for 👍 / 'n' for 👎): y

💾 Feedback saved successfully.
✅ Positive feedback saved to memory: Task def456 marked as success.

✅ Plan Execution Summary:
{ ... }


"""
import asyncio
from core.conversation_manager import ConversationManager

async def main():
    # Initialize conversation manager
    conversation_manager = ConversationManager()

    # Example user goal (you can replace this with any Kubernetes-related request)
    #user_goal = "Scale nginx deployment to 5 replicas and restart the service"
    user_goal = "list pods in default namespace"

    # Run the full conversation cycle
    response = await conversation_manager.run_conversation(user_goal)
    print(f"\n🛠️ Agent Response:\n{response}\n")

if __name__ == "__main__":
    asyncio.run(main())
