import json
import os
from typing import Dict, List, Any, Optional

class ProductService:
    """Mock product service for accessing product catalog."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_data()
    
    def _load_data(self):
        """Load product data from JSON files."""
        with open(os.path.join(self.data_dir, "product_catalog.json"), "r") as f:
            self.product_catalog = json.load(f)
        
        # Create a flat list of all products for easier searching
        self.all_products = []
        for category, products in self.product_catalog.items():
            for product in products:
                product_with_category = product.copy()
                product_with_category["category"] = category
                self.all_products.append(product_with_category)
    
    def get_product_catalog(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get the full product catalog by category."""
        return self.product_catalog
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details by ID."""
        for product in self.all_products:
            if product["id"] == product_id:
                return product
        return None
    
    def get_products_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all products in a specific category."""
        return self.product_catalog.get(category, [])
    
    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search for products by name or description."""
        query = query.lower()
        results = []
        
        for product in self.all_products:
            if (query in product["name"].lower() or 
                query in product["description"].lower()):
                results.append(product)
        
        return results