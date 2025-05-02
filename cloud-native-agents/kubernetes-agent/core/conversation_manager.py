# kubernetes_agent/core/conversation_manager.py
import datetime
import time
import traceback
import uuid
from core.agent import get_kubernetes_agent
from planning.planner import get_planner
from planning.task_executor import get_task_executor
from feedback_learning.feedback_collector import FeedbackCollector
from feedback_learning.feedback_store import FeedbackStore
from feedback_learning.learning_manager import LearningManager
from memory.short_term_memory import get_short_term_memory
from memory.long_term_memory import get_long_term_memory

# Import monitoring components
from monitoring.agent_logger import get_logger
from monitoring.cost_tracker import get_cost_tracker
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger

from reflection.reflection_engine import get_reflection_engine


class ConversationManager:
    """Coordinates full Kubernetes agent lifecycle for a user goal."""

    def __init__(self):
        # Initialize monitoring tools
        self.logger = get_logger(__name__)
        self.cost_tracker = get_cost_tracker()
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        self.reflection_engine = get_reflection_engine()
        
        self.logger.info("Initializing ConversationManager")
        
        # Track initialization time
        start_time = time.time()
        
        try:
            # Agent Initialization
            self.logger.info("Creating KubernetesAgent")
            self.agent_obj = get_kubernetes_agent()
            self.kube_agent = self.agent_obj.get_agent()
            self.executor_agent = self.agent_obj.get_executor_agent()

            # Planner and Executor
            self.logger.info("Creating Planner and TaskExecutor")
            self.planner = get_planner()
            self.executor = get_task_executor()

            # Memory Managers
            self.logger.info("Initializing Memory components")
            self.short_term_memory = get_short_term_memory()
            self.long_term_memory = get_long_term_memory()

            # Feedback and Learning
            self.logger.info("Initializing Feedback and Learning components")
            self.feedback_collector = FeedbackCollector()
            self.feedback_store = FeedbackStore()
            self.learning_manager = LearningManager()

            # Generate a unique conversation ID
            self.conversation_id = str(uuid.uuid4())
            self.logger.info("ConversationManager initialized with ID: %s", self.conversation_id)
            
            # Log initialization event
            self.audit.log_event("conversation_manager_initialized", {
                "conversation_id": self.conversation_id,
                "components": ["agent", "planner", "executor", "memory", "feedback", "learning"]
            })
            
            # Record successful initialization in metrics
            end_time = time.time()
            self.metrics.record_task_duration("conversation_manager_init", start_time, end_time)
        except Exception as e:
            self.logger.error("Failed to initialize ConversationManager: %s", str(e))
            traceback.print_exc()
            
            # Log initialization error
            self.audit.log_event("initialization_error", {
                "component": "conversation_manager",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
            # Record failed initialization in metrics
            self.metrics.record_tool_result("conversation_manager_init", False)
            
            raise

    async def run_conversation(self, user_goal: str, goal_category: str = "general"):
        """Main method to orchestrate full flow for a given user goal."""
        self.logger.info("Starting conversation for goal: %s", user_goal)
        # Track conversation execution time
        conversation_start = time.time()
        
        # Create unique IDs for this conversation
        session_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        
        # Get current hour for time-based metrics
        current_hour = datetime.datetime.now().hour
        hour_label = f"{current_hour:02d}:00"
        
        # Set conversation metadata for metrics enrichment
        self.metrics.set_conversation_metadata(conversation_id, {
            "goal_category": goal_category,
            "session_id": session_id,
            "hour_of_day": hour_label,
            "start_time": conversation_start
        })
        
        # Audit the conversation start with enhanced metadata
        self.audit.log_event("conversation_started", {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "user_goal": user_goal,
            "goal_category": goal_category,
            "hour_of_day": hour_label
        })
        
        try:
            # Step 1: Create short-term session memory
            memory_start = time.time()
            session_id = self.short_term_memory.start_session()
            memory_end = time.time()
            
            # Record session creation time with labels
            self.metrics.record_task_duration(
                "memory_session_creation", 
                memory_start, 
                memory_end,
                goal_category=goal_category
            )
            self.logger.info("Created memory session with ID: %s", session_id)

            # Step 2: Plan tasks based on goal with enhanced categorization
            planning_start = time.time()
            plan = await self.planner.create_plan(user_goal, goal_category=goal_category)
            planning_end = time.time()
            
            # Record planning metrics with enhanced labels
            self.metrics.record_task_duration(
                "planning", 
                planning_start, 
                planning_end,
                goal_category=goal_category
            )

            # Add the goal and metadata to the plan for memory storage
            plan["goal"] = user_goal
            plan["goal_category"] = goal_category
            plan["conversation_id"] = conversation_id
            plan["hour_of_day"] = hour_label

            self.logger.info("Created plan with ID: %s containing %d tasks", 
                        plan.get("plan_id"), len(plan["tasks"]))
            
            # Record plan creation metrics
            self.metrics.record_tool_result(
                "plan_creation", 
                True,
                goal_category=goal_category
            )

            task_results = []

            # Log task details with priorities
            for idx, task in enumerate(plan["tasks"], 1):
                self.logger.info("Task %d: %s (Priority: %d)", 
                                idx, task['description'], task.get('priority', idx))
                
                # Set task metadata for metrics
                self.metrics.set_task_metadata(task["id"], {
                    "goal_category": goal_category,
                    "plan_id": plan["plan_id"],
                    "conversation_id": conversation_id,
                    "priority": task.get('priority', idx),
                    "task_number": idx,
                    "total_tasks": len(plan["tasks"]),
                    "hour_of_day": hour_label
                })

            # Step 3: Execute each task with enhanced monitoring
            for idx, task in enumerate(plan["tasks"], 1):
                task_id = task["id"]
                task_description = task["description"]
                self.logger.info("Executing task %d/%d: %s (id: %s)", 
                            idx, len(plan["tasks"]), task_description, task_id)
                
                # Track task execution time
                task_start = time.time()
        
                # Execute the task using agent and tool mapping - no special cases
                try:
                    # Log task start in audit with enhanced metadata
                    self.audit.log_task_execution(
                        plan_id=plan["plan_id"],
                        task_id=task_id,
                        task_text=task_description,
                        goal_category=goal_category,
                        priority=task.get('priority', idx)
                    )
                    
                    # Record tool call with task ID and conversation ID
                    self.metrics.record_tool_call(
                        f"task_execution_{idx}",
                        task_id=task_id,
                        conversation_id=conversation_id
                    )
                    
                    # Execute the task
                    result = await self.executor.execute_task(
                        task, 
                        self.kube_agent, 
                        self.executor_agent,
                        goal_category=goal_category,
                        conversation_id=conversation_id
                    )
                    
                    # Record successful execution with labels
                    self.metrics.record_tool_result(
                        f"task_{idx}", 
                        True,
                        goal_category=goal_category
                    )
                    
                    # Calculate task duration
                    task_end = time.time()
                    task_duration = task_end - task_start
                    
                    # Record task timing with enhanced labels
                    self.metrics.record_task_duration(
                        task_id, 
                        task_start, 
                        task_end,
                        goal_category=goal_category
                    )
                    
                    # Record duration in histogram metric
                    if hasattr(self.metrics, 'record_duration_histogram'):
                        self.metrics.record_duration_histogram(
                            "task_execution",
                            task_duration,
                            {
                                "task_id": task_id,
                                "goal_category": goal_category,
                                "task_number": idx,
                                "total_tasks": len(plan["tasks"])
                            }
                        )
                    
                    # Log successful task completion with enhanced details
                    self.logger.info("Task %s completed successfully in %.2f seconds", 
                                task_id, task_duration)
                    
                    task_results.append({
                        "id": task_id,
                        "description": task.get("description"),
                        "response": result,
                        "status": True,
                        "duration": task_duration,
                        "goal_category": goal_category,
                        "task_number": idx,
                        "total_tasks": len(plan["tasks"])
                    })
                    
                except Exception as e:
                    self.logger.error("Error executing task %s: %s", task_id, str(e))
                    error_type = type(e).__name__
                    traceback.print_exc()
                    
                    # Record failure with categorization
                    self.metrics.record_tool_result(
                        f"task_{idx}", 
                        False,
                        goal_category=goal_category
                    )
                    
                    # Log failure event with enhanced details
                    self.audit.log_event("task_execution_error", {
                        "plan_id": plan["plan_id"],
                        "task_id": task_id,
                        "error": str(e),
                        "error_type": error_type,
                        "goal_category": goal_category,
                        "task_number": idx,
                        "total_tasks": len(plan["tasks"])
                    })
                    
                    # Calculate task duration even for failed tasks
                    task_end = time.time()
                    task_duration = task_end - task_start

                    task_results.append({
                        "id": task_id,
                        "description": task_description,
                        "response": {"error": str(e), "traceback": traceback.format_exc()},
                        "status": False,
                        "duration": task_duration,
                        "goal_category": goal_category,
                        "error_type": error_type
                    })

            reflection_summary = await self.reflection_engine.reflect_on_tasks(
                task_results=task_results,
                plan_id=plan["plan_id"],
                session_id=session_id,
                goal=user_goal,
                agent=self.kube_agent,
                executor_agent=self.executor_agent,
                goal_category="kubernetes"
            )

            # Optional: print insight summary
            self.logger.info("\n🧠 Agent Self-Reflection Summary:")
            for insight in reflection_summary["insights"]:
                self.logger.info("- %s", insight)

            # Create the full response with enhanced metadata
            full_response = {
                "session_id": session_id,
                "conversation_id": conversation_id,
                "plan_id": plan.get("plan_id"),
                "goal": user_goal,
                "goal_category": goal_category,
                "tasks": task_results,
                "hour_of_day": hour_label,
                "success_rate": sum(1 for t in task_results if t["status"]) / len(task_results) if task_results else 0
            }
            
            # Store in long-term memory with performance tracking
            memory_store_start = time.time()
            await self.long_term_memory.store_plan_summary_v2(full_response)
            memory_store_end = time.time()

            # Record memory storage metrics with labels
            self.metrics.record_task_duration(
                "memory_storage", 
                memory_store_start, 
                memory_store_end,
                goal_category=goal_category
            )
            self.logger.info("Stored conversation results in long-term memory")
            
            # Calculate total conversation time
            conversation_end = time.time()
            total_duration = conversation_end - conversation_start
            
            # Record total conversation metrics with enhanced labels
            self.metrics.record_task_duration(
                "total_conversation", 
                conversation_start, 
                conversation_end,
                goal_category=goal_category
            )
            
            # Also record under specific conversation ID for individual tracking
            self.metrics.record_task_duration(
                f"conversation_{conversation_id}", 
                conversation_start, 
                conversation_end,
                goal_category=goal_category
            )
            
            # Record hour_of_day label for time analysis
            if hasattr(self.metrics, 'record_label'):
                self.metrics.record_label(
                    f"conversation_{conversation_id}",
                    "hour_of_day",
                    hour_label
                )
            
            # Log conversation completion with detailed metrics
            self.logger.info("Conversation completed in %.2f seconds with %d tasks (%d successful, %d failed)",
                        total_duration,
                        len(task_results),
                        sum(1 for t in task_results if t["status"]),
                        sum(1 for t in task_results if not t["status"]))
            
            # Audit conversation completion with comprehensive details
            self.audit.log_event("conversation_completed", {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "duration_seconds": round(total_duration, 2),
                "task_count": len(task_results),
                "success_count": sum(1 for t in task_results if t["status"]),
                "failure_count": sum(1 for t in task_results if not t["status"]),
                "success_rate": round(sum(1 for t in task_results if t["status"]) / len(task_results), 2) if task_results else 0,
                "total_llm_cost": self.cost_tracker.get_total_cost(),
                "goal_category": goal_category,
                "hour_of_day": hour_label
            })
            
            # Get total token usage and create metrics
            total_tokens = sum(
                self.metrics.metrics["llm_tokens_used"].values()
            )
            
            # Log token and cost summary
            self.logger.info("Total tokens used: %d, Estimated cost: $%.6f", 
                        total_tokens, self.cost_tracker.get_total_cost())
            
            # TODO: Add optional feedback collection here
            # self._collect_user_feedback(conversation_id, task_results)
                        
            return self.combine_task_results(full_response["tasks"])
        except Exception as e:
            # Handle conversation-level errors with comprehensive instrumentation
            self.logger.error("Error in conversation execution: %s", str(e))
            error_type = type(e).__name__
            traceback.print_exc()
            
            # Log conversation error with detailed categorization
            self.audit.log_event("conversation_error", {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "user_goal": user_goal,
                "goal_category": goal_category,
                "error": str(e),
                "error_type": error_type,
                "traceback": traceback.format_exc(),
                "hour_of_day": hour_label
            })
            
            # Calculate conversation duration even for failed conversation
            conversation_end = time.time()
            total_duration = conversation_end - conversation_start
            
            # Record failure metrics with enhanced labels
            self.metrics.record_task_duration(
                "failed_conversation", 
                conversation_start, 
                conversation_end,
                goal_category=goal_category
            )
            self.metrics.record_tool_result(
                "conversation_execution", 
                False,
                goal_category=goal_category
            )
            
            return f"## ❌ Error in Conversation\n\nThe agent encountered an error: {str(e)}\n\nPlease try again or contact the administrator."
    
    def combine_task_results(self, response_data: list) -> str:
        """
        Combine all task results into a single Markdown-formatted summary.
        """
        self.logger.info("Generating combined task results summary for %d tasks", len(response_data))
        combined_sections = ["## ✅ Final Plan Summary\n"]

        for idx, task in enumerate(response_data, 1):
            task_id = task["id"]
            task_description = task["description"]
            task_status = task["status"]
            # Handle both success and error cases
            if task_status and "result" in task["response"]:
                task_response = task["response"]["result"]
            elif not task_status and "error" in task["response"]:
                task_response = f"**ERROR:** {task['response']['error']}"
            else:
                task_response = "No response data available"
            # Add duration if available
            duration_text = ""
            if "duration" in task:
                duration_text = f" (completed in {task['duration']:.2f}s)"
                
            task_status_emoji = "✅" if task_status else "❌"
            task_header = f"### 🔹 Task {idx}: {task_description} {task_status_emoji}{duration_text}"
            task_output = f"{task_header}\n\n{task_response}\n"
            combined_sections.append(task_output)

        # Add a summary section with metrics
        success_count = sum(1 for t in response_data if t["status"])
        fail_count = len(response_data) - success_count
        total_duration = sum(t.get("duration", 0) for t in response_data)
        
        metrics_summary = (
            f"## 📊 Execution Metrics\n\n"
            f"- **Tasks:** {len(response_data)} total ({success_count} successful, {fail_count} failed)\n"
            f"- **Total Duration:** {total_duration:.2f} seconds\n"
            f"- **Estimated LLM Cost:** ${self.cost_tracker.get_total_cost():.6f}\n"
        )
        
        combined_sections.append(metrics_summary)

        return "\n---\n\n".join(combined_sections)