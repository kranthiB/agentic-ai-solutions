import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

class CalendarService:
    """Mock calendar service for accessing meeting data."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_data()
    
    def _load_data(self):
        """Load meeting data from JSON files."""
        with open(os.path.join(self.data_dir, "upcoming_meetings.json"), "r") as f:
            self.meetings = json.load(f)
    
    def get_meeting_by_id(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting details by ID."""
        for meeting in self.meetings:
            if meeting["id"] == meeting_id:
                return meeting
        return None
    
    def get_upcoming_meetings(self, days: int = 14) -> List[Dict[str, Any]]:
        """Get all upcoming meetings within a time window."""
        today = datetime.now()
        cutoff = today.replace(hour=0, minute=0, second=0, microsecond=0).toordinal() + days
        
        upcoming = []
        for meeting in self.meetings:
            date = datetime.strptime(meeting["date"], "%Y-%m-%d")
            if date.toordinal() >= today.toordinal() and date.toordinal() <= cutoff:
                upcoming.append(meeting)
        
        return upcoming
    
    def get_customer_meetings(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all meetings for a specific customer."""
        return [m for m in self.meetings if m["customer_id"] == customer_id]