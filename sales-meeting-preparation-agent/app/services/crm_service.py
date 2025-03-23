import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

class CRMService:
    """Mock CRM service for accessing customer data."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_data()
    
    def _load_data(self):
        """Load customer data from JSON files."""
        with open(os.path.join(self.data_dir, "customers.json"), "r") as f:
            self.customers = json.load(f)
        
        with open(os.path.join(self.data_dir, "interactions.json"), "r") as f:
            self.interactions = json.load(f)
        
        with open(os.path.join(self.data_dir, "transactions.json"), "r") as f:
            self.transactions = json.load(f)
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer details by ID."""
        for customer in self.customers:
            if customer["id"] == customer_id:
                return customer
        return None
    
    def get_all_customers(self) -> List[Dict[str, Any]]:
        """Get all customers."""
        return self.customers
    
    def get_customer_interactions(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all interactions for a customer."""
        return [i for i in self.interactions if i["customer_id"] == customer_id]
    
    def get_customer_transactions(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all transactions for a customer."""
        return [t for t in self.transactions if t["customer_id"] == customer_id]
    
    def get_recent_interactions(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent interactions across all customers."""
        today = datetime.now()
        cutoff = today.replace(hour=0, minute=0, second=0, microsecond=0).toordinal() - days
        
        recent = []
        for interaction in self.interactions:
            date = datetime.strptime(interaction["date"], "%Y-%m-%d")
            if date.toordinal() >= cutoff:
                recent.append(interaction)
        
        return recent
