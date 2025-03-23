import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, List, Dict, Any
import json
import uvicorn
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.agent import SalesMeetingAgent
from app.services.crm_service import CRMService
from app.services.calendar_service import CalendarService
from app.services.product_service import ProductService
from app.utils.vector_store import get_vector_store

app = FastAPI(title="Sales Meeting Preparation Agent")

# Mount static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/web/templates")

# Initialize services
crm_service = CRMService("data/crm")
calendar_service = CalendarService("data/calendar")
product_service = ProductService("data/products")

# Initialize agent
vector_store = get_vector_store()
agent = SalesMeetingAgent(
    crm_service=crm_service,
    calendar_service=calendar_service,
    product_service=product_service,
    vector_store=vector_store
)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Get upcoming meetings
    upcoming_meetings = calendar_service.get_upcoming_meetings()
    
    # Sort by date
    upcoming_meetings.sort(key=lambda x: f"{x['date']} {x['time']}")
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "meetings": upcoming_meetings}
    )

@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
async def meeting_preparation(request: Request, meeting_id: str):
    # Get meeting details
    meeting = calendar_service.get_meeting_by_id(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get customer details
    customer = crm_service.get_customer_by_id(meeting["customer_id"])
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Generate meeting preparation
    preparation = agent.prepare_for_meeting(meeting_id)
    
    return templates.TemplateResponse(
        "meeting_preparation.html", 
        {
            "request": request, 
            "meeting": meeting,
            "customer": customer,
            "preparation": preparation
        }
    )

@app.get("/customer/{customer_id}", response_class=HTMLResponse)
async def customer_detail(request: Request, customer_id: str):
    # Get customer details
    customer = crm_service.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get customer interactions
    interactions = crm_service.get_customer_interactions(customer_id)
    
    # Get customer transactions
    transactions = crm_service.get_customer_transactions(customer_id)
    
    return templates.TemplateResponse(
        "customer_detail.html", 
        {
            "request": request, 
            "customer": customer,
            "interactions": interactions,
            "transactions": transactions
        }
    )

@app.post("/feedback", response_class=RedirectResponse)
async def submit_feedback(
    meeting_id: str = Form(...),
    recommendation_id: str = Form(...),
    rating: int = Form(...),
    comments: Optional[str] = Form(None)
):
    # Store feedback (in a real implementation, this would persist)
    agent.store_feedback(meeting_id, recommendation_id, rating, comments)
    
    # Redirect back to meeting page
    return RedirectResponse(f"/meeting/{meeting_id}", status_code=303)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)