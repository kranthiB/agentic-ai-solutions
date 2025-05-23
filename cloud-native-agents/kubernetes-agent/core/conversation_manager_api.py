# kubernetes_agent/core/conversation_manager_api.py
"""
Extended ConversationManager with API integration support.
This version adds WebSocket status updates for frontend integration.
"""

import datetime
import time
import traceback
from typing import Optional, List, Dict, Any
import uuid

# Import original conversation manager
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

# Import guardrail service
from services.guardrail.guardrail_service import get_guardrail_service

# Import services
from services.conversation.conversation_service import get_conversation_service

# Import API bridge for WebSocket updates
try:
    import api_bridge
    WEBSOCKET_ENABLED = True
except ImportError:
    WEBSOCKET_ENABLED = False

class ConversationManagerAPI:
    """Extended Kubernetes agent conversation manager with API and WebSocket support."""

    def __init__(self):
        # Initialize monitoring tools
        self.logger = get_logger(__name__)
        self.cost_tracker = get_cost_tracker()
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        self.reflection_engine = get_reflection_engine()
        
        # Initialize guardrail service
        self.guardrail_service = get_guardrail_service()
        
        # Initialize conversation service
        self.conversation_service = get_conversation_service()
        
        self.logger.info("Initializing ConversationManagerAPI with WebSocket integration")
        
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
            self.executor = get_task_executor(config_path=None)

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
            self.logger.info("ConversationManagerAPI initialized with ID: %s", self.conversation_id)
            
            # Log initialization event
            self.audit.log_event("conversation_manager_initialized", {
                "conversation_id": self.conversation_id,
                "components": ["agent", "planner", "executor", "memory", "feedback", "learning", "guardrails"],
                "websocket_enabled": WEBSOCKET_ENABLED
            })
            
            # Record successful initialization in metrics
            end_time = time.time()
            self.metrics.record_task_duration("conversation_manager_init", start_time, end_time)
        except Exception as e:
            self.logger.error("Failed to initialize ConversationManagerAPI: %s", str(e))
            traceback.print_exc()
            
            # Log initialization error
            self.audit.log_event("initialization_error", {
                "component": "conversation_manager_api",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
            # Record failed initialization in metrics
            self.metrics.record_tool_result("conversation_manager_init", False)
            
            raise

    async def run_conversation(self, user_goal: str, goal_category: str = "general", conversation_id: str = None):
        """
        Main method to orchestrate full flow for a given user goal.
        
        Args:
            user_goal: The user's goal or query
            goal_category: Category of the goal (kubernetes, general, etc.)
            conversation_id: Optional conversation ID for API integration
            
        Returns:
            Combined task results as a formatted string
        """
        # Use provided conversation_id or generate a new one
        self.logger.info("In run conversations, Is web socket enabled?: %s", WEBSOCKET_ENABLED)
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
            
        self.logger.info("Starting conversation %s for goal: %s", conversation_id, user_goal)
        
        # Validate user goal through guardrails
        is_valid, reason = await self.guardrail_service.validate_user_input(
            user_input=user_goal,
            user_id="conversation_manager",
            conversation_id=conversation_id,
            metadata={"goal_category": goal_category}
        )
        
        # Check if goal was blocked by guardrails
        if not is_valid:
            # Check enforcement level
            config = self.guardrail_service.config
            if config.get("enforcement_level") == "block":
                self.logger.warning(f"Conversation goal blocked by guardrails: {reason}")
                self.audit.log_event("guardrail_blocked_conversation", {
                    "conversation_id": conversation_id,
                    "goal": user_goal,
                    "reason": reason,
                    "goal_category": goal_category
                })
                
                # Return a blocked message
                return f"## ⚠️ Conversation Goal Blocked\n\nThe requested goal could not be processed due to safety guardrails: {reason}\n\nPlease rephrase your request in a way that follows our safety guidelines."
            else:
                # Log warning but continue
                self.logger.warning(f"Guardrail warning for conversation goal (non-blocking): {reason}")
        
        # Track conversation execution time
        conversation_start = time.time()
        
        # Create unique IDs for this conversation
        session_id = str(uuid.uuid4())
        
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
        
        # Send WebSocket notification that agent is thinking
        if WEBSOCKET_ENABLED:
            try:
                await api_bridge.send_thinking_status(conversation_id, True)
            except Exception as e:
                self.logger.error(f"Error sending thinking status: {str(e)}")
        
        try:
            # Step 1: Create short-term session memory
            memory_start = time.time()
            session_id = self.short_term_memory.start_session()
            
            # Store the initial user goal in short-term memory
            self.short_term_memory.store_message(
                session_id=session_id,
                message={
                    "role": "user",
                    "content": user_goal,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
            # Store additional context information
            self.short_term_memory.store_context_item(
                session_id=session_id,
                item_type="conversation_metadata",
                data={
                    "conversation_id": conversation_id,
                    "goal_category": goal_category,
                    "session_start": datetime.datetime.now().isoformat()
                }
            )
            
            memory_end = time.time()
            
            # Record session creation time with labels
            self.metrics.record_task_duration(
                "memory_session_creation", 
                memory_start, 
                memory_end,
                goal_category=goal_category
            )
            self.logger.info("Created memory session with ID: %s", session_id)

            # Check for similar past conversations to inform planning
            similar_conversations = []
            try:
                similar_conversations = await self.long_term_memory.retrieve_similar_conversations(
                    goal=user_goal,
                    limit=3
                )
                
                if similar_conversations:
                    self.logger.info(f"Found {len(similar_conversations)} similar past conversations for context")
                    
                    # Store similar conversations in short-term memory
                    self.short_term_memory.store_context_item(
                        session_id=session_id,
                        item_type="similar_conversations",
                        data=similar_conversations
                    )
            except Exception as e:
                self.logger.warning(f"Error retrieving similar conversations: {str(e)}")

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
            plan["session_id"] = session_id

            self.logger.info("Created plan with ID: %s containing %d tasks", 
                        plan.get("plan_id"), len(plan["tasks"]))
            
            # Store the plan in short-term memory
            self.short_term_memory.store_context_item(
                session_id=session_id,
                item_type="plan",
                data={
                    "plan_id": plan["plan_id"],
                    "tasks": plan["tasks"],
                    "created_at": datetime.datetime.now().isoformat()
                }
            )
            
            # Record plan creation metrics
            self.metrics.record_tool_result(
                "plan_creation", 
                True,
                goal_category=goal_category
            )

            # Send WebSocket update with plan details
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.send_plan_update(
                        conversation_id=conversation_id,
                        plan_id=plan["plan_id"],
                        tasks=plan["tasks"]
                    )
                    
                    # Update session state with plan details
                    await api_bridge.update_session_state(
                        conversation_id=conversation_id,
                        state_update={
                            "goal": user_goal,
                            "goal_category": goal_category,
                            "plan_id": plan["plan_id"],
                            "task_count": len(plan["tasks"]),
                            "current_task_index": 0,
                            "status": "planning_complete"
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Error sending plan update: {str(e)}")
            
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
                
                # Send WebSocket update for task status - pending
                if WEBSOCKET_ENABLED:
                    try:
                        await api_bridge.update_task_progress(
                            conversation_id=conversation_id,
                            task_id=task["id"],
                            task_description=task["description"],
                            status="pending",
                            progress_percentage=0.0
                        )
                    except Exception as e:
                        self.logger.error(f"Error sending task pending update: {str(e)}")

            # Step 3: Execute each task with enhanced monitoring
            for idx, task in enumerate(plan["tasks"], 1):
                task_id = task["id"]
                task_description = task["description"]
                self.logger.info("Executing task %d/%d: %s (id: %s)", 
                            idx, len(plan["tasks"]), task_description, task_id)
                
                # Send WebSocket update for task status - in progress
                if WEBSOCKET_ENABLED:
                    try:
                        await api_bridge.update_task_progress(
                            conversation_id=conversation_id,
                            task_id=task_id,
                            task_description=task_description,
                            status="in_progress",
                            progress_percentage=50.0
                        )
                        
                        # Send progress update
                        progress_percentage = ((idx - 1 + 0.5) / len(plan["tasks"])) * 100
                        await api_bridge.broadcast_progress_update(
                            conversation_id=conversation_id,
                            progress_type="conversation",
                            percentage=progress_percentage,
                            current_step=idx,
                            total_steps=len(plan["tasks"]),
                            step_description=f"Executing task: {task_description}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error sending task in-progress update: {str(e)}")
                
                # Track task execution time
                task_start = time.time()
                
                # Add session_id to task context
                if "context" not in task:
                    task["context"] = {}
                task["context"]["session_id"] = session_id
        
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
                    
                    # Send WebSocket update for task status - completed
                    if WEBSOCKET_ENABLED:
                        try:
                            await api_bridge.update_task_progress(
                                conversation_id=conversation_id,
                                task_id=task_id,
                                task_description=task_description,
                                status="completed",
                                progress_percentage=100.0,
                                result={"response": result}
                            )
                            
                            # Send conversation progress update
                            progress_percentage = (idx / len(plan["tasks"])) * 100
                            await api_bridge.broadcast_progress_update(
                                conversation_id=conversation_id,
                                progress_type="conversation",
                                percentage=progress_percentage,
                                current_step=idx,
                                total_steps=len(plan["tasks"]),
                                step_description=f"Completed task: {task_description}"
                            )
                        except Exception as e:
                            self.logger.error(f"Error sending task completion update: {str(e)}")
                    
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
                    
                    # Send WebSocket update for task status - failed
                    if WEBSOCKET_ENABLED:
                        try:
                            await api_bridge.update_task_progress(
                                conversation_id=conversation_id,
                                task_id=task_id,
                                task_description=task_description,
                                status="failed",
                                progress_percentage=100.0,
                                result={"error": str(e)}
                            )
                        except Exception as ws_error:
                            self.logger.error(f"Error sending task failure update: {str(ws_error)}")
                    
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

            # Run reflection on tasks
            reflection_summary = await self.reflection_engine.reflect_on_tasks(
                task_results=task_results,
                plan_id=plan["plan_id"],
                session_id=session_id,
                goal=user_goal,
                agent=self.kube_agent,
                executor_agent=self.executor_agent,
                goal_category=goal_category
            )
            
            # Store reflection insights in short-term memory
            self.short_term_memory.store_context_item(
                session_id=session_id,
                item_type="reflection_insights",
                data=reflection_summary["insights"]
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
                "success_rate": sum(1 for t in task_results if t["status"]) / len(task_results) if task_results else 0,
                "reflection_insights": reflection_summary.get("insights", [])
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
            
            # Send WebSocket notification that agent is done thinking
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.send_thinking_status(conversation_id, False)
                    
                    # Update final session state
                    await api_bridge.update_session_state(
                        conversation_id=conversation_id,
                        state_update={
                            "status": "completed",
                            "completed_at": datetime.datetime.now().isoformat(),
                            "duration_seconds": round(total_duration, 2),
                            "success_rate": round(sum(1 for t in task_results if t["status"]) / len(task_results), 2) if task_results else 0
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Error sending thinking status update: {str(e)}")
            
            # Get total token usage and create metrics
            total_tokens = sum(
                self.metrics.metrics["llm_tokens_used"].values()
            )
            
            # Log token and cost summary
            self.logger.info("Total tokens used: %d, Estimated cost: $%.6f", 
                        total_tokens, self.cost_tracker.get_total_cost())
            
            # Generate the combined results
            result_text = self.combine_task_results(full_response["tasks"])
            
            # Store the assistant's response in short-term memory
            self.short_term_memory.store_message(
                session_id=session_id,
                message={
                    "role": "assistant",
                    "content": result_text,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
            # Validate final output through guardrails before returning
            is_valid, reason, filtered_output = await self.guardrail_service.validate_llm_output(
                output=result_text,
                context={"conversation_id": conversation_id, "goal_category": goal_category}
            )
            
            # Use filtered output if modified
            if not is_valid:
                self.logger.info(f"Conversation output modified by guardrails: {reason}")
                result_text = filtered_output
                
            return result_text
            
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
            
            # Send WebSocket error notification
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.send_error(
                        conversation_id=conversation_id,
                        error_message=f"Error processing conversation: {str(e)}",
                        error_code=error_type
                    )
                    await api_bridge.send_thinking_status(conversation_id, False)
                    
                    # Update session state with error
                    await api_bridge.update_session_state(
                        conversation_id=conversation_id,
                        state_update={
                            "status": "error",
                            "error": str(e),
                            "error_type": error_type,
                            "error_time": datetime.datetime.now().isoformat()
                        }
                    )
                except Exception as ws_error:
                    self.logger.error(f"Error sending error update via WebSocket: {str(ws_error)}")
            
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
    
    async def process_followup(self, conversation_id: str, query: str) -> str:
        """
        Process a follow-up question for an existing conversation
        
        Args:
            conversation_id: ID of the existing conversation
            query: Follow-up question or request
            
        Returns:
            Response text
        """
        self.logger.info(f"Processing follow-up query for conversation {conversation_id}: {query}")
        
        # Validate follow-up query through guardrails
        is_valid, reason = await self.guardrail_service.validate_user_input(
            user_input=query,
            user_id="conversation_manager",
            conversation_id=conversation_id,
            metadata={"query_type": "followup"}
        )
        
        # Check if query was blocked by guardrails
        if not is_valid:
            # Check enforcement level
            config = self.guardrail_service.config
            if config.get("enforcement_level") == "block":
                self.logger.warning(f"Follow-up query blocked by guardrails: {reason}")
                self.audit.log_event("guardrail_blocked_followup", {
                    "conversation_id": conversation_id,
                    "query": query,
                    "reason": reason
                })
                
                # Return a blocked message
                return f"## ⚠️ Follow-Up Query Blocked\n\nYour follow-up question could not be processed due to safety guardrails: {reason}\n\nPlease rephrase your question in a way that follows our safety guidelines."
            else:
                # Log warning but continue
                self.logger.warning(f"Guardrail warning for follow-up query (non-blocking): {reason}")
        
        # Send WebSocket notification that agent is thinking
        if WEBSOCKET_ENABLED:
            try:
                await api_bridge.send_thinking_status(conversation_id, True)
                
                # Update session state
                await api_bridge.update_session_state(
                    conversation_id=conversation_id,
                    state_update={
                        "status": "processing_followup",
                        "followup_query": query,
                        "followup_start": datetime.datetime.now().isoformat()
                    }
                )
            except Exception as e:
                self.logger.error(f"Error sending thinking status: {str(e)}")
        
        try:
            # Retrieve conversation context from memory
            conversation = await self.conversation_service.get_conversation(conversation_id)
            if not conversation:
                self.logger.error(f"Conversation {conversation_id} not found")
                return f"Unable to process follow-up: conversation {conversation_id} not found"
            
            # Get conversation messages for context
            messages = await self.conversation_service.list_messages(conversation_id)
            if not messages:
                self.logger.warning(f"No messages found for conversation {conversation_id}")
            
            # Get session from short-term memory if available
            session_id = conversation.get("session_id")
            session_context = []
            if session_id:
                session_context = self.short_term_memory.get_context(session_id)
                
                # Store the follow-up question in short-term memory
                self.short_term_memory.store_message(
                    session_id=session_id,
                    message={
                        "role": "user",
                        "content": query,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "type": "followup"
                    }
                )
            else:
                self.logger.warning(f"No session ID found for conversation {conversation_id}")
                # Create a new session if needed
                session_id = self.short_term_memory.start_session()
                self.logger.info(f"Created new session {session_id} for followup on conversation {conversation_id}")
                
                # Store conversation metadata and follow-up question
                self.short_term_memory.store_context_item(
                    session_id=session_id,
                    item_type="conversation_metadata",
                    data={
                        "conversation_id": conversation_id,
                        "goal_category": conversation.get("goal_category", "general"),
                        "session_start": datetime.datetime.now().isoformat(),
                        "is_followup_session": True
                    }
                )
                
                self.short_term_memory.store_message(
                    session_id=session_id,
                    message={
                        "role": "user",
                        "content": query,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "type": "followup"
                    }
                )
            
            # Look for similar past conversations
            similar_conversations = []
            try:
                similar_conversations = await self.long_term_memory.retrieve_similar_conversations(
                    goal=query,
                    limit=2
                )
                if similar_conversations:
                    self.logger.info(f"Found {len(similar_conversations)} similar conversations for followup context")
                    
                    # Store in short-term memory
                    if session_id:
                        self.short_term_memory.store_context_item(
                            session_id=session_id,
                            item_type="similar_conversations",
                            data=similar_conversations
                        )
            except Exception as e:
                self.logger.warning(f"Error retrieving similar conversations for followup: {str(e)}")
            
            # Build context from conversation history
            context = {
                "goal": conversation.get("goal", ""),
                "goal_category": conversation.get("goal_category", "general"),
                "history": messages,
                "session_context": session_context,
                "similar_conversations": similar_conversations,
                "session_id": session_id
            }
            
            # Log context retrieval
            self.logger.info(f"Retrieved context for conversation {conversation_id}: {len(messages)} messages, {len(session_context)} session items")
            
            # Create a task that includes the conversation context
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "description": f"Answer follow-up question: {query}",
                "priority": 1,
                "status": "PENDING",
                "context": context
            }
            
            # Track task execution time
            task_start = time.time()
            
            # Send WebSocket update for task status - in progress
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.update_task_progress(
                        conversation_id=conversation_id,
                        task_id=task_id,
                        task_description=task["description"],
                        status="in_progress",
                        progress_percentage=50.0
                    )
                except Exception as e:
                    self.logger.error(f"Error sending task in-progress update: {str(e)}")
            
            # Execute the task
            result = await self.executor.execute_task(
                task, 
                self.kube_agent, 
                self.executor_agent,
                goal_category=conversation.get("goal_category", "general"),
                conversation_id=conversation_id
            )
            
            # Calculate task duration
            task_end = time.time()
            task_duration = task_end - task_start
            
            # Send WebSocket update for task status - completed
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.update_task_progress(
                        conversation_id=conversation_id,
                        task_id=task_id,
                        task_description=task["description"],
                        status="completed",
                        progress_percentage=100.0,
                        result={"response": result}
                    )
                    
                    # Update session state
                    await api_bridge.update_session_state(
                        conversation_id=conversation_id,
                        state_update={
                            "status": "followup_completed",
                            "followup_completion_time": datetime.datetime.now().isoformat(),
                            "followup_duration": task_duration
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Error sending task completion update: {str(e)}")
            
            # Send WebSocket notification that agent is done thinking
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.send_thinking_status(conversation_id, False)
                except Exception as e:
                    self.logger.error(f"Error sending thinking status update: {str(e)}")
            
            # Get final result text
            if isinstance(result, dict) and "result" in result:
                result_text = result["result"]
            else:
                result_text = str(result)
            
            # Store the response in short-term memory
            if session_id:
                self.short_term_memory.store_message(
                    session_id=session_id,
                    message={
                        "role": "assistant",
                        "content": result_text,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "type": "followup_response"
                    }
                )
                
            # Validate final output through guardrails before returning
            is_valid, reason, filtered_output = await self.guardrail_service.validate_llm_output(
                output=result_text,
                context={"conversation_id": conversation_id, "query_type": "followup"}
            )
            
            # Use filtered output if modified
            if not is_valid:
                self.logger.info(f"Follow-up output modified by guardrails: {reason}")
                result_text = filtered_output
            
            return result_text
            
        except Exception as e:
            self.logger.error(f"Error processing follow-up query: {str(e)}")
            traceback.print_exc()
            
            # Send WebSocket error notification
            if WEBSOCKET_ENABLED:
                try:
                    await api_bridge.send_error(
                        conversation_id=conversation_id,
                        error_message=f"Error processing follow-up: {str(e)}",
                        error_code=type(e).__name__
                    )
                    await api_bridge.send_thinking_status(conversation_id, False)
                    
                    # Update session state with error
                    await api_bridge.update_session_state(
                        conversation_id=conversation_id,
                        state_update={
                            "status": "followup_error",
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "error_time": datetime.datetime.now().isoformat()
                        }
                    )
                except Exception as ws_error:
                    self.logger.error(f"Error sending error update via WebSocket: {str(ws_error)}")
            
            return f"## ❌ Error Processing Follow-up\n\nThe agent encountered an error: {str(e)}\n\nPlease try again with a different question."
    
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
    
# Singleton instance
_conversation_manager_api: Optional[ConversationManagerAPI] = None


def get_conversation_manager_api() -> ConversationManagerAPI:
    global _conversation_manager_api
    if _conversation_manager_api is None:
        _conversation_manager_api = ConversationManagerAPI()
    return _conversation_manager_api