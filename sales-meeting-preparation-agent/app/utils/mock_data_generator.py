# app/utils/mock_data_generator.py
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import random
import argparse

# Define region-specific data dictionaries
REGION_DATA = {
    "USA": {
        "company_names": [
            "American Construction Corp", "Elite Design Studio", "Metro Public Schools", 
            "Oceanview Hotels Group", "Greenfield Landscaping", "Cornerstone Development",
            "Liberty Contractors", "Starlight Interiors", "Vista Property Management",
            "Northstar Building Solutions"
        ],
        "person_names": [
            "John Smith", "Emily Johnson", "Robert Williams", "Lisa Chen", "Michael Garcia",
            "Jessica Brown", "David Miller", "Sarah Wilson", "James Taylor", "Jennifer Davis"
        ],
        "locations": [
            "Chicago, IL", "New York, NY", "Boston, MA", "Miami, FL", "Austin, TX",
            "San Francisco, CA", "Seattle, WA", "Denver, CO", "Atlanta, GA", "Phoenix, AZ"
        ],
        "currency": "USD",
        "currency_symbol": "$",
        "phone_format": "555-###-####",
        "projects": {
            "Construction": ["suburban housing development", "downtown office renovation", "industrial warehouse construction", "shopping mall expansion"],
            "Interior Design": ["luxury condominium redesign", "upscale restaurant interior", "corporate headquarters styling", "boutique hotel rooms"],
            "Education": ["public school renovation", "university campus refresh", "sports facility update", "administration building modernization"],
            "Hospitality": ["beach resort renovation", "downtown hotel update", "steakhouse redesign", "convention center refresh"],
            "Landscaping": ["residential garden project", "commercial property landscaping", "public park renovation", "golf course maintenance"]
        }
    },
    "INDIA": {
        "company_names": [
            "Bharat Constructions", "Elegant Interiors", "Metro Education Society", 
            "Taj Hospitality Group", "Green Earth Landscaping", "Sunrise Developers",
            "Reliable Contractors", "Amrit Design Studio", "Prism Property Services",
            "Ashoka Building Solutions"
        ],
        "person_names": [
            "Rajesh Kumar", "Priya Sharma", "Vikram Patel", "Anita Singh", "Suresh Mehta",
            "Neha Gupta", "Amit Verma", "Sunita Reddy", "Rahul Joshi", "Deepa Chakraborty"
        ],
        "locations": [
            "Mumbai, Maharashtra", "Delhi, NCR", "Bangalore, Karnataka", "Hyderabad, Telangana", "Chennai, Tamil Nadu",
            "Pune, Maharashtra", "Kolkata, West Bengal", "Ahmedabad, Gujarat", "Jaipur, Rajasthan", "Kochi, Kerala"
        ],
        "currency": "INR",
        "currency_symbol": "₹",
        "phone_format": "+91 ##### #####",
        "projects": {
            "Construction": ["township development", "IT park construction", "commercial complex building", "residential high-rise"],
            "Interior Design": ["luxury apartment styling", "premium restaurant design", "corporate office interiors", "heritage hotel renovation"],
            "Education": ["school campus renovation", "university building refresh", "sports complex update", "administrative block modernization"],
            "Hospitality": ["resort renovation", "business hotel update", "fine dining restaurant redesign", "convention hall refresh"],
            "Landscaping": ["farmhouse garden project", "corporate campus landscaping", "municipal park development", "temple grounds maintenance"]
        }
    },
    "APAC": {
        "company_names": [
            "Asia Pacific Builders", "Orient Design Studio", "East West Education Group", 
            "Pacific Rim Hospitality", "Harmony Landscaping", "Bamboo Development",
            "Dragon Contractors", "Sakura Interiors", "Eastern Star Properties",
            "Golden Bridge Construction"
        ],
        "person_names": [
            "Wei Chen", "Sakura Tanaka", "Min-ho Kim", "Mei Ling Wong", "Raj Patel",
            "Ji-eun Park", "Hiroshi Nakamura", "Lakshmi Nair", "Xiao Wang", "Nguyen Tran"
        ],
        "locations": [
            "Singapore", "Tokyo, Japan", "Seoul, South Korea", "Hong Kong", "Bangkok, Thailand",
            "Shanghai, China", "Kuala Lumpur, Malaysia", "Manila, Philippines", "Jakarta, Indonesia", "Taipei, Taiwan"
        ],
        "currency": "Multiple",
        "currency_symbol": "$",
        "phone_format": "+## ### ### ####",
        "projects": {
            "Construction": ["high-rise apartment complex", "technology park development", "commercial tower construction", "mixed-use development"],
            "Interior Design": ["luxury residence styling", "hotel chain standardization", "multinational office design", "shopping mall interior"],
            "Education": ["international school renovation", "university campus modernization", "technology center development", "language academy design"],
            "Hospitality": ["beach resort renovation", "business hotel chain update", "fine dining franchise design", "convention center modernization"],
            "Landscaping": ["tropical garden design", "commercial complex landscaping", "public water garden development", "corporate campus environments"]
        }
    },
    "ANZ": {
        "company_names": [
            "Aussie Construction Group", "Kiwi Design Studio", "Southern Cross Education", 
            "Pacific Hospitality Holdings", "Down Under Landscaping", "Oceanic Developers",
            "Outback Contractors", "Harbor City Interiors", "Tasman Property Management",
            "Wellington Building Solutions"
        ],
        "person_names": [
            "James Wilson", "Emma Thompson", "Jack Robinson", "Olivia Mitchell", "William Taylor",
            "Charlotte Anderson", "Thomas Campbell", "Jessica Martin", "Oliver Davies", "Sophie Clark"
        ],
        "locations": [
            "Sydney, NSW", "Melbourne, VIC", "Brisbane, QLD", "Perth, WA", "Adelaide, SA",
            "Auckland, NZ", "Wellington, NZ", "Christchurch, NZ", "Gold Coast, QLD", "Canberra, ACT"
        ],
        "currency": "AUD/NZD",
        "currency_symbol": "$",
        "phone_format": "+61 # #### ####",
        "projects": {
            "Construction": ["beachfront development", "urban apartment construction", "outback commercial complex", "sports stadium renovation"],
            "Interior Design": ["coastal residence styling", "winery restaurant design", "corporate headquarters update", "boutique hotel concept"],
            "Education": ["primary school modernization", "university campus redevelopment", "sports academy facilities", "technical college update"],
            "Hospitality": ["harbor view hotel renovation", "winery tourism facilities", "seafood restaurant redesign", "conference center development"],
            "Landscaping": ["drought-resistant garden design", "native flora landscaping", "public park renovation", "coastal property environments"]
        }
    },
    "MEA": {
        "company_names": [
            "Al Faisal Construction", "Mediterranean Design Studio", "Gulf Education Institute", 
            "Sahara Hospitality Group", "Oasis Landscaping", "Atlas Development",
            "Pyramid Contractors", "Arabian Interiors", "Levant Property Services",
            "Al Jazeera Building Solutions"
        ],
        "person_names": [
            "Mohammed Al-Farsi", "Fatima Hassan", "Ahmed El-Masri", "Leila Karimi", "Yusuf Ibrahim",
            "Noor Al-Sayed", "Omar Sheikh", "Aisha Mahmoud", "Tariq Rahman", "Zainab Al-Mansour"
        ],
        "locations": [
            "Dubai, UAE", "Cairo, Egypt", "Riyadh, Saudi Arabia", "Doha, Qatar", "Johannesburg, South Africa",
            "Istanbul, Turkey", "Casablanca, Morocco", "Abu Dhabi, UAE", "Nairobi, Kenya", "Tel Aviv, Israel"
        ],
        "currency": "Multiple",
        "currency_symbol": "$",
        "phone_format": "+### ## ### ####",
        "projects": {
            "Construction": ["luxury villa complex", "commercial tower development", "resort construction", "urban shopping district"],
            "Interior Design": ["royal residence styling", "desert resort interiors", "international hotel design", "commercial plaza concept"],
            "Education": ["international academy construction", "university campus modernization", "private school renovation", "research center development"],
            "Hospitality": ["beach resort renovation", "business hotel development", "heritage restaurant design", "conference facility construction"],
            "Landscaping": ["desert garden design", "water conservation landscaping", "royal palace grounds", "commercial complex environments"]
        }
    }
}

# Ensure directories exist
os.makedirs("data/crm", exist_ok=True)
os.makedirs("data/calendar", exist_ok=True)
os.makedirs("data/products", exist_ok=True)

# Get current date for dynamic generation
CURRENT_DATE = datetime.now()

def get_region_data(region_or_country):
    """Get region-specific data based on input parameter."""
    region_or_country = region_or_country.upper()
    if region_or_country in REGION_DATA:
        return REGION_DATA[region_or_country]
    else:
        print(f"Warning: Region/country '{region_or_country}' not found. Using USA as default.")
        return REGION_DATA["USA"]

def generate_customers(region_data, num_customers=5):
    """Generate customer data with region-specific information."""
    customers = []
    
    industries = ["Construction", "Interior Design", "Education", "Hospitality", "Landscaping"]
    segments = ["Commercial", "Residential", "Institutional", "Luxury Residential", "Industrial"]
    sizes = ["Small", "Medium", "Large"]
    
    for i in range(1, num_customers + 1):
        industry = random.choice(industries)
        
        # Randomly select company name and location from region-specific data
        company_name = random.choice(region_data["company_names"])
        if i > 1 and company_name in [c["name"] for c in customers]:
            # Avoid duplicate names by adding a suffix
            company_name = f"{company_name} {chr(64+i)}"
            
        location = random.choice(region_data["locations"])
        contact_name = random.choice(region_data["person_names"])
        
        # Generate a region-appropriate phone number
        phone_format = region_data["phone_format"]
        phone = ""
        for char in phone_format:
            if char == '#':
                phone += str(random.randint(0, 9))
            else:
                phone += char
        
        # Generate a reasonable relationship start date
        relationship_since = (CURRENT_DATE - timedelta(days=random.randint(365, 365*5))).strftime("%Y-%m-%d")
        
        customers.append({
            "id": f"C{i:03d}",
            "name": company_name,
            "industry": industry,
            "size": random.choice(sizes),
            "relationship_since": relationship_since,
            "primary_contact": {
                "name": contact_name,
                "title": random.choice(["Purchasing Manager", "Operations Director", "Facilities Manager", "Owner", "CEO", "Project Manager"]),
                "email": f"{contact_name.lower().replace(' ', '.')}@{company_name.lower().replace(' ', '')}.example",
                "phone": phone
            },
            "annual_revenue": random.randint(500, 25000) * 1000,
            "location": location,
            "segment": random.choice(segments)
        })
    
    return customers

# Define product categories and products (unchanged from original)
product_categories = {
    "Interior Paints": [
        {"id": "P001", "name": "UltraSheen Matte", "description": "Premium matte finish interior paint", "unit": "Gallon", "base_price": 45.99},
        {"id": "P002", "name": "UltraSheen Eggshell", "description": "Premium eggshell finish interior paint", "unit": "Gallon", "base_price": 48.99},
        {"id": "P003", "name": "UltraSheen Semi-Gloss", "description": "Premium semi-gloss finish interior paint", "unit": "Gallon", "base_price": 52.99},
        {"id": "P004", "name": "EcoChoice Low-VOC", "description": "Environmentally friendly low-VOC interior paint", "unit": "Gallon", "base_price": 56.99},
        {"id": "P005", "name": "KidProof Washable", "description": "Highly washable and durable interior paint", "unit": "Gallon", "base_price": 54.99}
    ],
    "Exterior Paints": [
        {"id": "P006", "name": "WeatherGuard Satin", "description": "Weather-resistant exterior paint with satin finish", "unit": "Gallon", "base_price": 58.99},
        {"id": "P007", "name": "WeatherGuard Flat", "description": "Weather-resistant exterior paint with flat finish", "unit": "Gallon", "base_price": 55.99},
        {"id": "P008", "name": "WeatherGuard Gloss", "description": "Weather-resistant exterior paint with gloss finish", "unit": "Gallon", "base_price": 62.99},
        {"id": "P009", "name": "ExtremeDurable Elastomeric", "description": "Highly flexible coating for exterior surfaces", "unit": "Gallon", "base_price": 75.99}
    ],
    "Specialty Coatings": [
        {"id": "P010", "name": "ConcreteShield", "description": "Heavy-duty coating for concrete floors", "unit": "Gallon", "base_price": 68.99},
        {"id": "P011", "name": "RustStop Metal Primer", "description": "Rust-inhibiting primer for metal surfaces", "unit": "Gallon", "base_price": 45.99},
        {"id": "P012", "name": "HeatResist 500", "description": "Heat-resistant coating for high-temperature areas", "unit": "Gallon", "base_price": 89.99}
    ],
    "Primers and Sealers": [
        {"id": "P013", "name": "AllSurface Primer", "description": "Universal primer for multiple surfaces", "unit": "Gallon", "base_price": 39.99},
        {"id": "P014", "name": "StainBlock Plus", "description": "Stain-blocking primer and sealer", "unit": "Gallon", "base_price": 42.99}
    ],
    "Accessories": [
        {"id": "P015", "name": "Premium Roller Set", "description": "Professional-grade roller and tray set", "unit": "Each", "base_price": 24.99},
        {"id": "P016", "name": "Precision Brush Pack", "description": "Set of various sizes of high-quality brushes", "unit": "Pack", "base_price": 32.99},
        {"id": "P017", "name": "Painter's Masking Tape", "description": "Professional-grade masking tape", "unit": "Roll", "base_price": 8.99}
    ]
}

# Flatten products list
def get_products():
    products = []
    for category, items in product_categories.items():
        for product in items:
            product_copy = product.copy()
            product_copy["category"] = category
            products.append(product_copy)
    return products

# Define interaction types and templates
interaction_types = ["Meeting", "Phone Call", "Email", "Site Visit", "Product Demo"]
interaction_templates = {
    "Meeting": [
        "Discussed {product} for upcoming project. {contact} expressed interest in durability and price point.",
        "Presented color options for {product}. {contact} leaning toward neutral palette for their {project}.",
        "Reviewed specifications of {product}. {contact} had concerns about application in humid conditions.",
        "Introduced new {product} line. {contact} requested samples to evaluate with their team."
    ],
    "Phone Call": [
        "Quick call with {contact} about {product} availability for urgent {project}.",
        "{contact} called with questions about maintenance of {product} after installation.",
        "Follow-up call discussing {product} pricing for bulk order for {project}.",
        "{contact} requested technical specs for {product} via email."
    ],
    "Email": [
        "Sent {contact} requested information about {product} technical specifications.",
        "{contact} emailed asking for color samples of {product} for their {project}.",
        "Provided quote to {contact} for {product} for upcoming {project}.",
        "Shared maintenance guidelines for {product} with {contact}."
    ],
    "Site Visit": [
        "Visited {project} site with {contact} to assess requirements for {product} application.",
        "On-site consultation for {project}. Recommended {product} based on conditions observed.",
        "Evaluated existing surfaces at {project} with {contact}. Suggested {product} for optimal results.",
        "Site inspection with {contact} revealed moisture issues. Recommended {product} with additional sealant."
    ],
    "Product Demo": [
        "Demonstrated application techniques for {product} to {contact} and their team.",
        "Conducted color consultation using {product} samples. {contact} selected finalists for their {project}.",
        "Performed adhesion test of {product} on substrate samples from {project}.",
        "Showcased durability features of {product} compared to competitor products. {contact} was impressed."
    ]
}

# Generate past interactions with dynamic dates and region-specific projects
def generate_interactions(customers, products, region_data):
    all_interactions = []
    interaction_id = 1
    
    # Use dynamic date range based on current date
    end_date = CURRENT_DATE
    
    for customer in customers:
        # Determine number of interactions based on relationship length
        relationship_start = datetime.strptime(customer["relationship_since"], "%Y-%m-%d")
        relationship_duration = (end_date - relationship_start).days
        
        # More established customers have more interactions
        num_interactions = min(50, max(5, relationship_duration // 30))
        
        # Generate random interaction dates between relationship start and now
        interaction_dates = []
        date_range = (end_date - relationship_start).days
        for _ in range(num_interactions):
            days_ago = random.randint(0, date_range)
            interaction_date = end_date - timedelta(days=days_ago)
            interaction_dates.append(interaction_date)
        
        # Sort by date (oldest to newest)
        interaction_dates = sorted(interaction_dates)
        
        # Customer's industry-specific projects from regional data
        industry = customer["industry"]
        customer_projects = region_data["projects"].get(
            industry, 
            ["construction project", "renovation project", "painting project"]
        )
        
        # Track which products this customer has shown interest in or purchased
        customer_products = set()
        
        # Generate interactions
        for date in interaction_dates:
            # Occasional interactions don't mention specific products (general relationship building)
            if random.random() < 0.2:
                interaction_type = random.choice(interaction_types)
                notes = f"General check-in with {customer['primary_contact']['name']}. Discussed upcoming needs and maintained relationship."
                product_mentioned = None
            else:
                # Select a product, with higher probability for previously mentioned products
                if customer_products and random.random() < 0.6:
                    product_id = random.choice(list(customer_products))
                    # Find the full product object for this ID
                    product_mentioned = next((p for p in products if p["id"] == product_id), None)
                    if product_mentioned is None:
                        # Fallback in case product isn't found
                        product_mentioned = random.choice(products)
                else:
                    product_mentioned = random.choice(products)
                    customer_products.add(product_mentioned["id"])
                
                interaction_type = random.choice(interaction_types)
                
                # Generate notes using templates
                template = random.choice(interaction_templates[interaction_type])
                project = random.choice(customer_projects)
                notes = template.format(
                    product=product_mentioned["name"], 
                    contact=customer["primary_contact"]["name"],
                    project=project
                )
                
                # Add some sentiment occasionally
                if random.random() < 0.3:
                    sentiments = [
                        " Customer seemed very satisfied with our previous products.",
                        " There were some concerns about price point.",
                        " They mentioned they're also considering competitor products.",
                        " Customer emphasized timeline constraints for delivery.",
                        " They expressed strong preference for our brand over competitors."
                    ]
                    notes += random.choice(sentiments)
            
            interaction = {
                "id": f"INT{interaction_id:04d}",
                "customer_id": customer["id"],
                "date": date.strftime("%Y-%m-%d"),
                "type": interaction_type,
                "participants": [customer["primary_contact"]["name"], "Sales Representative"],
                "notes": notes,
                "product_id": product_mentioned["id"] if product_mentioned else None
            }
            
            all_interactions.append(interaction)
            interaction_id += 1
    
    return all_interactions

# Generate transactions/orders with dynamic dates and region-specific currency formatting
def generate_transactions(customers, products, interactions, region_data):
    transactions = []
    transaction_id = 1
    
    # Currency symbol for formatting
    currency_symbol = region_data["currency_symbol"]
    
    for customer in customers:
        # Determine number of transactions based on customer size
        if customer["size"] == "Large":
            num_transactions = random.randint(8, 15)
        elif customer["size"] == "Medium":
            num_transactions = random.randint(5, 10)
        else:
            num_transactions = random.randint(2, 7)
        
        # Customer's interactions to extract product interests
        customer_interactions = [i for i in interactions if i["customer_id"] == customer["id"]]
        
        # Extract products mentioned in interactions
        product_interests = [i["product_id"] for i in customer_interactions if i["product_id"]]
        
        # Get interaction dates to align transactions
        interaction_dates = [datetime.strptime(i["date"], "%Y-%m-%d") for i in customer_interactions]
        
        # No transactions if no interactions
        if not interaction_dates:
            continue
            
        for _ in range(num_transactions):
            # Transactions usually occur after interactions discussing products
            # Pick a random interaction date and add a few days
            base_date = random.choice(interaction_dates)
            transaction_date = base_date + timedelta(days=random.randint(3, 14))
            
            # Make sure transaction date isn't in the future
            if transaction_date > CURRENT_DATE:
                transaction_date = CURRENT_DATE - timedelta(days=random.randint(1, 7))
            
            # Transaction details
            line_items = []
            
            # Number of products in this transaction
            num_products = random.randint(1, 5)
            
            # Prefer products the customer has shown interest in
            if product_interests and random.random() < 0.8:
                # Select products of interest, with possible repeats
                for _ in range(min(num_products, len(product_interests))):
                    product_id = random.choice(product_interests)
                    product = next((p for p in products if p["id"] == product_id), None)
                    
                    if product:
                        quantity = random.randint(1, 10)
                        unit_price = product["base_price"] * (1 - random.uniform(0, 0.15))  # Apply some discount
                        
                        line_items.append({
                            "product_id": product["id"],
                            "product_name": product["name"],
                            "quantity": quantity,
                            "unit_price": round(unit_price, 2),
                            "extended_price": round(quantity * unit_price, 2)
                        })
            
            # Add some random products if needed
            while len(line_items) < num_products:
                product = random.choice(products)
                
                quantity = random.randint(1, 10)
                unit_price = product["base_price"] * (1 - random.uniform(0, 0.15))  # Apply some discount
                
                line_items.append({
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": quantity,
                    "unit_price": round(unit_price, 2),
                    "extended_price": round(quantity * unit_price, 2)
                })
            
            # Calculate total
            total_amount = sum(item["extended_price"] for item in line_items)
            
            transaction = {
                "id": f"TRX{transaction_id:04d}",
                "customer_id": customer["id"],
                "date": transaction_date.strftime("%Y-%m-%d"),
                "status": "Completed",
                "currency_symbol": currency_symbol,
                "currency": region_data["currency"],
                "line_items": line_items,
                "total_amount": round(total_amount, 2)
            }
            
            transactions.append(transaction)
            transaction_id += 1
    
    return transactions

# Generate upcoming meetings for calendar with dynamic dates and region-specific locations
def generate_upcoming_meetings(customers):
    upcoming_meetings = []
    meeting_id = 1
    
    # Generate meetings for the next 14 days from current date
    today = CURRENT_DATE
    
    for customer in customers:
        # 80% chance each customer has an upcoming meeting
        if random.random() < 0.8:
            # Meeting date in the next 1-14 days
            meeting_date = today + timedelta(days=random.randint(1, 14))
            
            # Different meeting types
            meeting_types = ["Quarterly Review", "Product Consultation", "Project Planning", "Follow-up", "New Product Introduction"]
            
            # Determine location based on customer's location
            possible_locations = ["Customer Office", "Video Call", "Phone Call", "ABC Paints Office"]
            # Add weight to customer office if customer has a location
            if customer.get("location"):
                possible_locations.extend(["Customer Office"] * 2)
            
            meeting = {
                "id": f"MTG{meeting_id:04d}",
                "customer_id": customer["id"],
                "customer_name": customer["name"],
                "contact_name": customer["primary_contact"]["name"],
                "date": meeting_date.strftime("%Y-%m-%d"),
                "time": f"{random.randint(8, 16):02d}:00",
                "duration_minutes": random.choice([30, 60, 90]),
                "type": random.choice(meeting_types),
                "location": random.choice(possible_locations),
                "description": f"Meeting with {customer['name']} to discuss their current and upcoming needs."
            }
            
            upcoming_meetings.append(meeting)
            meeting_id += 1
    
    return upcoming_meetings

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate mock data for ABC Paints Sales Meeting Preparation Agent')
    parser.add_argument('--region', default='USA', help='Region or country to generate data for (USA, INDIA, APAC, ANZ, MEA)')
    args = parser.parse_args()
    
    # Get region-specific data
    region_data = get_region_data(args.region)
    
    print(f"Generating mock data for region: {args.region}")
    
    # Generate data
    customers = generate_customers(region_data)
    products = get_products()
    interactions = generate_interactions(customers, products, region_data)
    transactions = generate_transactions(customers, products, interactions, region_data)
    upcoming_meetings = generate_upcoming_meetings(customers)
    
    # Organize products by category for output
    products_by_category = {}
    for product in products:
        category = product["category"]
        if category not in products_by_category:
            products_by_category[category] = []
        products_by_category[category].append(product)
    
    # Save all data to files
    def save_to_json(data, filename):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    save_to_json(customers, "data/crm/customers.json")
    save_to_json(interactions, "data/crm/interactions.json")
    save_to_json(transactions, "data/crm/transactions.json")
    save_to_json(products_by_category, "data/products/product_catalog.json")
    save_to_json(upcoming_meetings, "data/calendar/upcoming_meetings.json")
    
    print(f"Mock data generation complete with current date: {CURRENT_DATE.strftime('%Y-%m-%d')}")
    print(f"Generated data for region: {args.region}")
    print(f"Generated {len(customers)} customers, {len(interactions)} interactions, {len(transactions)} transactions, and {len(upcoming_meetings)} upcoming meetings")

if __name__ == "__main__":
    main()