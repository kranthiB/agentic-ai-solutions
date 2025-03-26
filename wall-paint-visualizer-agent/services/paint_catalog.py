import json
import os
from typing import Dict, List, Optional

class PaintCatalog:
    """
    Mock service for Paints color catalog
    """
    
    def __init__(self, catalog_path: str = None):
        """
        Initialize the paint catalog
        
        Args:
            catalog_path: Path to the JSON catalog file. If None, uses mock data.
        """
        self.colors = {}
        
        if catalog_path and os.path.exists(catalog_path):
            with open(catalog_path, 'r') as f:
                self.colors = json.load(f)
        else:
            # Mock color data if no catalog file is provided
            self._initialize_mock_catalog()
    
    def _initialize_mock_catalog(self):
        """Create a mock catalog with sample colors"""
        # Sample colors with hex codes, names, and metadata
        mock_colors = [
            {
                "id": "NW001",
                "name": "Arctic White",
                "hex_code": "#F5F5F5",
                "rgb": [245, 245, 245],
                "family": "Whites",
                "description": "A pure, clean white that brightens any room",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss", "gloss"],
                "popular_rooms": ["kitchen", "bathroom", "bedroom"],
                "properties": {
                    "light_reflectance": 92,
                    "coverage": "excellent",
                    "base_type": "white"
                }
            },
            {
                "id": "BL118",
                "name": "Ocean Blue",
                "hex_code": "#4F84C4",
                "rgb": [79, 132, 196],
                "family": "Blues",
                "description": "A calming medium blue inspired by coastal waters",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss"],
                "popular_rooms": ["bedroom", "bathroom", "living room"],
                "properties": {
                    "light_reflectance": 48,
                    "coverage": "good",
                    "base_type": "medium"
                }
            },
            {
                "id": "GN205",
                "name": "Sage Meadow",
                "hex_code": "#9CAF88",
                "rgb": [156, 175, 136],
                "family": "Greens",
                "description": "A soft, muted green that brings nature indoors",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss"],
                "popular_rooms": ["living room", "bedroom", "dining room"],
                "properties": {
                    "light_reflectance": 56,
                    "coverage": "good",
                    "base_type": "medium"
                }
            },
            {
                "id": "GY133",
                "name": "Metropolitan Gray",
                "hex_code": "#C0C0C0",
                "rgb": [192, 192, 192],
                "family": "Grays",
                "description": "A versatile medium gray that complements any décor",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss", "gloss"],
                "popular_rooms": ["living room", "office", "kitchen"],
                "properties": {
                    "light_reflectance": 65,
                    "coverage": "excellent",
                    "base_type": "light"
                }
            },
            {
                "id": "RD078",
                "name": "Crimson Splendor",
                "hex_code": "#C53151",
                "rgb": [197, 49, 81],
                "family": "Reds",
                "description": "A bold, energetic red that makes a statement",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss"],
                "popular_rooms": ["dining room", "accent wall", "entryway"],
                "properties": {
                    "light_reflectance": 35,
                    "coverage": "medium",
                    "base_type": "deep"
                }
            },
            {
                "id": "YL042",
                "name": "Sunlit Meadow",
                "hex_code": "#F0E68C",
                "rgb": [240, 230, 140],
                "family": "Yellows",
                "description": "A cheerful, warm yellow that brightens any space",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss"],
                "popular_rooms": ["kitchen", "bathroom", "bedroom"],
                "properties": {
                    "light_reflectance": 78,
                    "coverage": "good",
                    "base_type": "light"
                }
            },
            {
                "id": "BR157",
                "name": "Cinnamon Spice",
                "hex_code": "#8B4513",
                "rgb": [139, 69, 19],
                "family": "Browns",
                "description": "A rich, warm brown that creates a cozy atmosphere",
                "finish_options": ["matte", "eggshell", "satin"],
                "popular_rooms": ["living room", "study", "dining room"],
                "properties": {
                    "light_reflectance": 22,
                    "coverage": "excellent",
                    "base_type": "deep"
                }
            },
            {
                "id": "BK001",
                "name": "Midnight Black",
                "hex_code": "#0A0A0A",
                "rgb": [10, 10, 10],
                "family": "Blacks",
                "description": "A deep, true black for dramatic effect",
                "finish_options": ["matte", "eggshell", "satin", "semi-gloss", "gloss"],
                "popular_rooms": ["accent wall", "trim", "doors"],
                "properties": {
                    "light_reflectance": 5,
                    "coverage": "excellent",
                    "base_type": "deep"
                }
            },
            {
                "id": "PP091",
                "name": "Lavender Dream",
                "hex_code": "#C8A2C8",
                "rgb": [200, 162, 200],
                "family": "Purples",
                "description": "A soft, romantic purple with gray undertones",
                "finish_options": ["matte", "eggshell", "satin"],
                "popular_rooms": ["bedroom", "bathroom", "nursery"],
                "properties": {
                    "light_reflectance": 62,
                    "coverage": "good",
                    "base_type": "medium"
                }
            },
            {
                "id": "OR064",
                "name": "Amber Glow",
                "hex_code": "#E49B0F",
                "rgb": [228, 155, 15],
                "family": "Oranges",
                "description": "A vibrant, warm orange with golden undertones",
                "finish_options": ["matte", "eggshell", "satin"],
                "popular_rooms": ["dining room", "kitchen", "accent wall"],
                "properties": {
                    "light_reflectance": 51,
                    "coverage": "good",
                    "base_type": "deep"
                }
            }
        ]
        
        # Convert to dictionary for faster lookup
        for color in mock_colors:
            self.colors[color["id"]] = color
    
    def get_all_colors(self) -> List[Dict]:
        """
        Get all available paint colors
        
        Returns:
            List of color dictionaries
        """
        return list(self.colors.values())
    
    def get_color_by_id(self, color_id: str) -> Optional[Dict]:
        """
        Get a specific paint color by ID
        
        Args:
            color_id: The unique identifier of the color
            
        Returns:
            Color dictionary if found, None otherwise
        """
        return self.colors.get(color_id)
    
    def search_colors(self, query: str) -> List[Dict]:
        """
        Search for colors by name, family, or description
        
        Args:
            query: Search term
            
        Returns:
            List of matching color dictionaries
        """
        query = query.lower()
        results = []
        
        for color in self.colors.values():
            if (query in color["name"].lower() or 
                query in color["family"].lower() or 
                query in color["description"].lower()):
                results.append(color)
        
        return results
    
    def get_colors_by_family(self, family: str) -> List[Dict]:
        """
        Get colors within a specific color family
        
        Args:
            family: Color family (e.g., "Blues", "Greens")
            
        Returns:
            List of color dictionaries in the specified family
        """
        family = family.lower()
        return [
            color for color in self.colors.values() 
            if color["family"].lower() == family
        ]
    
    def save_catalog(self, catalog_path: str):
        """
        Save the current catalog to a JSON file
        
        Args:
            catalog_path: Path to save the catalog JSON
        """
        with open(catalog_path, 'w') as f:
            json.dump(self.colors, f, indent=2)


if __name__ == "__main__":
    # Test the catalog
    catalog = PaintCatalog()
    all_colors = catalog.get_all_colors()
    print(f"Total colors: {len(all_colors)}")
    
    # Print some sample colors
    for i, color in enumerate(all_colors[:3]):
        print(f"Color {i+1}: {color['name']} ({color['id']}) - {color['hex_code']}")