# Sales Meeting Preparation Agent - POC

This proof of concept demonstrates an AI-powered sales meeting preparation agent for ABC Paints sales representatives. The agent analyzes customer data from multiple sources and provides comprehensive meeting preparation materials with transparent reasoning.

![SPA](https://raw.githubusercontent.com/kranthiB/tech-pulse/main/gif/SalesMeetingPreparationAgent.gif)

## Prerequisites

- Python 3.9+ installed
- Docker Desktop installed and running
- Git (optional)

## Setup Instructions

### 1. Clone or download the project

```
git clone https://github.com/kranthiB/agentic-ai-solutions.git
cd agentic-ai-solutions/sales-meeting-preparation-agent
```

### 2. Set up the Python environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip3.11 install -r requirements.txt
```

### 3. Generate mock data

```bash
# Run the mock data generator

# Generate data for India
python3.11 -m app.utils.mock_data_generator --region INDIA

# Generate data for USA
python3.11 -m app.utils.mock_data_generator --region USA

# Generate data for Asia-Pacific region
python3.11 -m app.utils.mock_data_generator --region APAC

# Generate data for Australia/New Zealand
python3.11 -m app.utils.mock_data_generator --region ANZ

# Generate data for Middle East and Africa
python3.11 -m app.utils.mock_data_generator --region MEA

```

### 4. Run the application using Docker

```bash
# Run the application locally
export HUGGINGFACEHUB_API_TOKEN="hf_xxxx"
python3.11 -m app.main
```

### 5. Access the application

Open your web browser and navigate to:
```
http://localhost:8000
```

## Using the POC

1. **View Upcoming Meetings**: The homepage displays all upcoming customer meetings.

2. **Prepare for a Meeting**: Click the "Prepare" button on any meeting card to generate preparation materials.

3. **Review Customer Profile**: Navigate to a customer's detailed profile by clicking "View Full Profile" on the meeting preparation page.

4. **Provide Feedback**: Rate the usefulness of recommendations to help improve future suggestions.

## Key Features Demonstrated

1. **Automated Meeting Preparation**: The agent automatically analyzes customer data and generates comprehensive preparation materials.

2. **Transparent Reasoning**: All recommendations include clear explanations of the reasoning and supporting evidence.

3. **Relationship Insights**: The agent identifies patterns in customer preferences, pain points, and purchase history.

4. **Next Steps Suggestions**: Clear guidance on follow-up actions after the meeting.

5. **Confidence Indicators**: Visual indicators of the agent's confidence in different recommendations.

6. **Feedback Collection**: Mechanism for sales representatives to provide feedback on recommendation quality.

## Technical Components

- **LangChain Framework**: Orchestrates the agent workflow and reasoning capabilities
- **Vector Database**: Enables semantic search across customer interactions and product information
- **Chain-of-Thought Reasoning**: Provides step-by-step explanations for all recommendations
- **Mock Services**: Simulates integration with CRM, calendar, and product catalog
- **FastAPI Web Application**: Delivers an intuitive interface for sales representatives

## Limitations of the POC

- Uses a simplified LLM model for demonstration purposes
- Relies on mock data rather than actual enterprise systems
- Limited personalization capabilities compared to the full implementation
- Reasoning explanations are less detailed than would be in production

## Next Steps for Full Implementation

1. Integration with actual enterprise systems (CRM, calendar, product database)
2. Implementation of more sophisticated reasoning with GPT-4 or equivalent
3. Development of comprehensive feedback loops and learning capabilities
4. Deployment of production-grade vector database and search capabilities
5. Implementation of personalization based on individual sales representative preferences