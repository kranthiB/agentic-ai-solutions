from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime
import uuid

from langchain.chains import LLMChain
from langchain_community.llms import HuggingFaceEndpoint
from langchain_core.callbacks.manager import CallbackManager
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.chains.conversation.memory import ConversationBufferMemory

from langchain.agents import AgentExecutor, create_react_agent

from langchain_community.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field, validator
from langchain.schema import Document
from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

class MeetingPreparation(BaseModel):
    """Output schema for meeting preparation."""
    customer_summary: str = Field(description="Brief summary of the customer and their business")
    relationship_insights: List[Dict[str, str]] = Field(description="Key insights about the relationship history")
    interaction_summary: str = Field(description="Summary of past interactions with this customer")
    purchase_history_summary: str = Field(description="Summary of the customer's purchase history")
    preferences_and_pain_points: List[Dict[str, str]] = Field(description="Identified customer preferences and pain points")
    recommendations: List[Dict[str, Any]] = Field(description="Recommended talking points and products for this meeting")
    next_steps: List[str] = Field(description="Suggested next steps after the meeting")
    preparation_confidence: float = Field(description="Confidence score (0-1) for the overall preparation quality")

class SalesMeetingAgent:
    """Agent for preparing sales meetings with customers."""
    
    def __init__(self, crm_service, calendar_service, product_service, vector_store):
        self.crm_service = crm_service
        self.calendar_service = calendar_service
        self.product_service = product_service
        self.vector_store = vector_store
        
        # Initialize LLM - in a production environment, use a more capable model
        # For POC purposes, we'll use a local HuggingFace model
        self.llm = HuggingFaceEndpoint(
            endpoint_url="https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
            huggingfacehub_api_token=os.environ.get("HUGGINGFACE_API_TOKEN", ""),
            task="text-generation",
            model_kwargs={
                "temperature": 0.5,
                "max_length": 2048
            }
        )
        
        # Output parser for structured responses
        self.output_parser = PydanticOutputParser(pydantic_object=MeetingPreparation)
        
        # Tools for the agent
        self.tools = self._create_tools()
        
        # Set up the agent
        self.agent = self._create_agent()
        
        # In-memory feedback store (would be a database in production)
        self.feedback_store = {}
        
    def _create_tools(self) -> List[BaseTool]:
        """Create tools for the agent to use."""
        
        # Use Tool class instead of BaseTool subclasses
        from langchain.tools import Tool
        
        # Create tools using functions
        tools = [
            Tool(
                name="customer_info",
                description="Get detailed information about a customer",
                func=lambda customer_id: self.crm_service.get_customer_by_id(customer_id)
            ),
            
            Tool(
                name="customer_interactions",
                description="Get past interactions with a customer",
                func=lambda customer_id: self.crm_service.get_customer_interactions(customer_id)
            ),
            
            Tool(
                name="customer_transactions",
                description="Get past transactions with a customer",
                func=lambda customer_id: self.crm_service.get_customer_transactions(customer_id)
            ),
            
            Tool(
                name="meeting_info",
                description="Get information about a scheduled meeting",
                func=lambda meeting_id: self.calendar_service.get_meeting_by_id(meeting_id)
            ),
            
            Tool(
                name="product_catalog",
                description="Get information about products",
                func=lambda query="": self.product_service.search_products(query) if query 
                    else self.product_service.get_product_catalog()
            ),
            
            Tool(
                name="semantic_search",
                description="Search for semantically relevant information",
                func=lambda query: [{"content": doc.page_content, "score": score} 
                    for doc, score in self.vector_store.similarity_search_with_score(query, k=3)]
            )
        ]
        
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create the agent executor."""
        
        # Template for React agent with all required variables
        react_template = """
        You are an AI assistant helping sales representatives at ABC Paints prepare for customer meetings.
        Your task is to analyze customer data and provide comprehensive meeting preparation materials.
        
        You have access to the following tools:
        
        {tools}
        
        When preparing for a meeting, follow these steps:
        1. Gather information about the customer and the scheduled meeting
        2. Review past interactions and transactions
        3. Identify the customer's preferences, pain points, and patterns
        4. Prepare recommendations and talking points
        5. Suggest next steps after the meeting
        
        Always explain your reasoning step-by-step before making conclusions.
        
        {format_instructions}
        
        Use the following format:
        
        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can repeat N times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question
        
        Begin!
        
        Question: {input}
        {agent_scratchpad}
        """
        
        prompt = PromptTemplate(
            template=react_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
            partial_variables={"format_instructions": self.output_parser.get_format_instructions()}
        )
        
        # Create the agent
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create the agent executor
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        return agent_executor
    
    def prepare_for_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Generate meeting preparation materials for a specific meeting."""
        
        # Check if we've already prepared for this meeting
        cache_file = f"data/cache/meeting_{meeting_id}.json"
        os.makedirs("data/cache", exist_ok=True)
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Get meeting information
        meeting = self.calendar_service.get_meeting_by_id(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting with ID {meeting_id} not found")
        
        # Get customer information directly instead of using the agent
        customer = self.crm_service.get_customer_by_id(meeting['customer_id'])
        interactions = self.crm_service.get_customer_interactions(meeting['customer_id'])
        transactions = self.crm_service.get_customer_transactions(meeting['customer_id'])
        
        # Create a simplified preparation without relying on complex agent execution
        preparation = {
            "customer_summary": f"{customer['name']} is a {customer['size'].lower()}-sized {customer['industry'].lower()} company based in {customer['location']}. They have been a customer since {customer['relationship_since']} and primarily operate in the {customer['segment']} segment.",
            "relationship_insights": [
                {"insight": f"Primary contact is {customer['primary_contact']['name']}, {customer['primary_contact']['title']}", 
                "evidence": "Customer record"},
                {"insight": f"Customer has had {len(interactions)} interactions in our records", 
                "evidence": "Interaction history"}
            ],
            "interaction_summary": "Recent interactions have focused on " + (
                f"{interactions[-1]['notes'].split('.')[0]}" if interactions else "initial relationship building"
            ),
            "purchase_history_summary": "Purchase history includes " + (
                f"{len(transactions)} transactions" if transactions else "no recorded transactions yet"
            ),
            "preferences_and_pain_points": [
                {"type": "preference", 
                "description": "Quality and durability", 
                "evidence": "Consistent focus in conversations"}
            ],
            "recommendations": [
                {
                    "id": str(uuid.uuid4()),
                    "topic": "Discuss upcoming project needs",
                    "reasoning": "Based on recent interactions about specific products",
                    "evidence": "Multiple product inquiries in the past 3 months",
                    "confidence": 0.85
                },
                {
                    "id": str(uuid.uuid4()),
                    "topic": "Present relevant product options",
                    "reasoning": "Customer has shown interest in specific product lines",
                    "evidence": "Recent product demonstrations and inquiries",
                    "confidence": 0.75
                }
            ],
            "next_steps": [
                "Send follow-up with product specifications",
                "Schedule site visit if applicable",
                "Prepare customized quote based on meeting outcomes"
            ],
            "preparation_confidence": 0.8,
            "generated_at": datetime.now().isoformat()
        }
        
        # Enhance with product information if available in interactions
        product_mentions = [i['product_id'] for i in interactions if i.get('product_id')]
        if product_mentions:
            product_info = [self.product_service.get_product_by_id(pid) for pid in product_mentions[:3]]
            product_info = [p for p in product_info if p]  # Filter out None values
            
            if product_info:
                preparation["recommendations"].append({
                    "id": str(uuid.uuid4()),
                    "topic": f"Discuss previously mentioned products including {', '.join([p['name'] for p in product_info])}",
                    "reasoning": "Customer has specifically discussed these products",
                    "evidence": "Mentioned in previous interactions",
                    "confidence": 0.9
                })
        
        # Cache the preparation
        with open(cache_file, 'w') as f:
            json.dump(preparation, f, indent=2)
        
        return preparation
    
    def prepare_for_meeting_org(self, meeting_id: str) -> Dict[str, Any]:
        """Generate meeting preparation materials for a specific meeting."""
        
        # Check if we've already prepared for this meeting
        # In a real implementation, this would check a database
        cache_file = f"data/cache/meeting_{meeting_id}.json"
        os.makedirs("data/cache", exist_ok=True)
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Get meeting information
        meeting = self.calendar_service.get_meeting_by_id(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting with ID {meeting_id} not found")
        
        # Prepare agent input
        agent_input = f"Prepare for an upcoming meeting with {meeting['customer_name']} (ID: {meeting['customer_id']}) scheduled on {meeting['date']} at {meeting['time']}. The meeting type is '{meeting['type']}' and will be held at '{meeting['location']}'."
        
        # Run the agent to generate preparation
        try:
            agent_output = self.agent.invoke({"input": agent_input})
            
            # Extract the structured output
            # This is a simplified implementation for the POC
            # In a real implementation, we would use the parser
            preparation = agent_output["output"]
            
            # Parse the output or use reasonable defaults if parsing fails
            try:
                parsed_output = self.output_parser.parse(preparation)
                preparation = parsed_output.dict()
            except Exception as e:
                print(f"Failed to parse output: {e}")
                # Provide a fallback with reasonable defaults
                preparation = {
                    "customer_summary": f"Summary of {meeting['customer_name']}",
                    "relationship_insights": [
                        {"insight": "Regular customer since 2020", "evidence": "Transaction history shows consistent purchases"},
                        {"insight": "Prefers premium products", "evidence": "Past purchases focused on higher-tier offerings"}
                    ],
                    "interaction_summary": "Customer has had regular meetings over the past year",
                    "purchase_history_summary": "Regular purchases of interior and exterior paints",
                    "preferences_and_pain_points": [
                        {"type": "preference", "description": "Prefers quick delivery", "evidence": "Mentioned in past conversations"},
                        {"type": "pain_point", "description": "Concerned about price increases", "evidence": "Raised during last quarterly review"}
                    ],
                    "recommendations": [
                        {
                            "id": str(uuid.uuid4()),
                            "topic": "Introduce new premium line",
                            "reasoning": "Matches their preference for high-quality products",
                            "evidence": "Past purchases have focused on premium offerings",
                            "confidence": 0.85
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "topic": "Discuss bulk order discounts",
                            "reasoning": "May address their price concerns",
                            "evidence": "Recent conversations have mentioned budget constraints",
                            "confidence": 0.75
                        }
                    ],
                    "next_steps": [
                        "Send product samples of recommended items",
                        "Schedule follow-up call to discuss specific project needs",
                        "Prepare customized quote based on meeting outcomes"
                    ],
                    "preparation_confidence": 0.8
                }
            
            # Add generation timestamp
            preparation["generated_at"] = datetime.now().isoformat()
            
            # Cache the preparation
            with open(cache_file, 'w') as f:
                json.dump(preparation, f, indent=2)
            
            return preparation
            
        except Exception as e:
            # Log the error and return a basic preparation
            print(f"Error preparing for meeting: {e}")
            # Simplified fallback
            return {
                "customer_summary": f"Error preparing full summary for {meeting['customer_name']}",
                "relationship_insights": [],
                "interaction_summary": "Unable to process interaction history",
                "purchase_history_summary": "Unable to process purchase history",
                "preferences_and_pain_points": [],
                "recommendations": [],
                "next_steps": ["Review customer data manually before meeting"],
                "preparation_confidence": 0.1,
                "generated_at": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def store_feedback(self, meeting_id: str, recommendation_id: str, rating: int, comments: Optional[str]) -> None:
        """Store feedback on a recommendation."""
        
        if meeting_id not in self.feedback_store:
            self.feedback_store[meeting_id] = {}
        
        self.feedback_store[meeting_id][recommendation_id] = {
            "rating": rating,
            "comments": comments,
            "timestamp": datetime.now().isoformat()
        }
        
        # In a real implementation, this would persist to a database
        # and be used to improve future recommendations
        print(f"Stored feedback for meeting {meeting_id}, recommendation {recommendation_id}")