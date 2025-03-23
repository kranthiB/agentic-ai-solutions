import os
from typing import Dict, List, Any, Optional
import json
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document

# Singleton pattern for vector store
_vector_store = None

def get_vector_store():
    """Get or initialize the vector store."""
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store
    
    # Check if the vector store exists
    if os.path.exists("data/vector_store") and os.listdir("data/vector_store"):
        # Load existing vector store
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        _vector_store = Chroma(persist_directory="data/vector_store", embedding_function=embeddings)
    else:
        # Create and populate vector store
        _vector_store = create_vector_store()
    
    return _vector_store

def create_vector_store():
    """Create and populate the vector store with documents."""
    os.makedirs("data/vector_store", exist_ok=True)
    
    # Load data
    documents = []
    
    # Load customer interactions
    if os.path.exists("data/crm/interactions.json"):
        with open("data/crm/interactions.json", "r") as f:
            interactions = json.load(f)
        
        for interaction in interactions:
            # Create document from interaction
            metadata = {
                "type": "interaction",
                "customer_id": interaction["customer_id"],
                "date": interaction["date"],
                "interaction_type": interaction["type"],
                "document_id": interaction["id"]
            }
            
            # Extract the content
            content = f"Interaction with customer {interaction['customer_id']} on {interaction['date']}: {interaction['notes']}"
            
            documents.append(Document(page_content=content, metadata=metadata))
    
    # Load product information
    if os.path.exists("data/products/product_catalog.json"):
        with open("data/products/product_catalog.json", "r") as f:
            product_catalog = json.load(f)
        
        for category, products in product_catalog.items():
            for product in products:
                # Create document from product
                metadata = {
                    "type": "product",
                    "category": category,
                    "document_id": product["id"],
                    "product_name": product["name"]
                }
                
                # Extract the content
                content = f"Product {product['name']} ({product['id']}): {product['description']}. Category: {category}. Price: ${product['base_price']} per {product['unit']}."
                
                documents.append(Document(page_content=content, metadata=metadata))
    
    # Create knowledge base documents with paint industry information
    # These would typically come from company documentation, but we'll create some samples
    knowledge_base = [
        {
            "title": "Interior Paint Application Best Practices",
            "content": """Best practices for interior paint application include:
            1. Properly prepare surfaces by cleaning and priming
            2. Use high-quality brushes and rollers appropriate for the finish
            3. Apply in thin, even coats rather than thick layers
            4. Allow adequate drying time between coats
            5. Maintain proper ventilation during and after application
            6. Store unused paint properly sealed in a temperature-controlled environment"""
        },
        {
            "title": "Exterior Paint Durability Factors",
            "content": """Factors affecting exterior paint durability:
            1. UV radiation exposure breaks down paint over time
            2. Moisture penetration can lead to peeling and blistering
            3. Temperature fluctuations cause expansion and contraction
            4. Proper surface preparation is critical for adhesion
            5. Quality of paint significantly impacts longevity
            6. Regular maintenance extends life expectancy of coating"""
        },
        {
            "title": "Commercial vs. Residential Paint Selection Guide",
            "content": """Key differences between commercial and residential paint selection:
            Commercial projects typically require:
            - Higher durability and washability
            - Faster drying times for efficient project completion
            - Low-VOC formulations for occupied spaces
            - Consistent batch color matching for large areas
            Residential projects typically prioritize:
            - Aesthetic appearance and color selection
            - Odor considerations for occupied homes
            - Cost-effectiveness for budget considerations
            - Specialized finishes for different rooms"""
        },
        {
            "title": "Paint Performance in High-Humidity Environments",
            "content": """Guidelines for paint performance in high-humidity environments:
            1. Mildew-resistant formulations are essential
            2. Semi-gloss or gloss finishes resist moisture better than flat
            3. Proper primer selection prevents substrate moisture issues
            4. Adequate dry time between coats prevents trapped moisture
            5. Specialized bathroom and kitchen paints contain additional mildewcides
            6. Proper ventilation during application and curing is critical"""
        },
        {
            "title": "Industrial Coating Selection for Chemical Exposure",
            "content": """Selection criteria for industrial coatings in chemical environments:
            1. Epoxy-based coatings offer excellent chemical resistance
            2. Polyurethane topcoats provide UV protection for outdoor applications
            3. Different chemicals require specific coating formulations
            4. Film thickness significantly impacts protective properties
            5. Surface preparation standards are more stringent than decorative applications
            6. Regular inspection and maintenance prevent catastrophic failures"""
        }
    ]
    
    for kb_doc in knowledge_base:
        metadata = {
            "type": "knowledge_base",
            "title": kb_doc["title"],
            "document_id": f"KB_{kb_doc['title'].replace(' ', '_')}"
        }
        
        documents.append(Document(page_content=kb_doc["content"], metadata=metadata))
    
    # Create the vector store
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory="data/vector_store"
    )
    
    # Persist to disk
    vector_store.persist()
    
    return vector_store