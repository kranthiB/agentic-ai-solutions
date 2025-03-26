# Wall Paint Visualizer Agent - POC

This proof of concept demonstrates an AI-powered room visualization solution for ABC Paints customers. The agent enables users to upload photos of their rooms and instantly visualize how different paint colors would appear on their walls, providing a confidence-building experience before making purchase decisions.

![Wall Paint Visualizer Agent](https://raw.githubusercontent.com/kranthiB/tech-pulse/main/gif/WallPaintVisualizerAgent.gif)

## Prerequisites

- Python 3.9+ installed
- Docker Desktop installed and running
- Git (optional)
- Approximately 4GB of free disk space for models and dependencies

## Setup Instructions

### 1. Clone or download the project

```
git clone https://github.com/kranthiB/agentic-ai-solutions.git
cd agentic-ai-solutions/wall-paint-visualizer-agent
```

### 2. Set up the Python environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip3.11 install -r requirements.txt
```

### 3. Run the application


```bash
# Run the backend app
python3.11 -m backend.main

# Run the frontend app
cd frontend
python -m http.server 8080
```

### 4. Access the application

Open your web browser and navigate to:
```
Frontend  - http://localhost:8080
Backend - http://localhost:8000
```

## Using the POC

1. **Upload Room Photo**: Click on the upload area to select a photo of your room, or drag and drop an image directly.

2. **Select Room Type and Lighting**: Choose the room type (living room, bedroom, etc.) and lighting conditions to improve visualization accuracy.

3. **Browse Paint Colors**: Explore the color catalog by using the color family filters or search functionality.

4. **Visualize Paint Colors**: Select a color and click "Visualize This Color" to see it applied to your room walls.

5. **Compare Multiple Colors**: Add colors to the comparison view to evaluate different options side by side.

## Key Features Demonstrated

1. **Photorealistic Visualization**: The agent generates realistic visualizations of rooms with new paint colors while preserving furniture and architectural elements.

2. **Color Accuracy**: All visualized colors precisely match ABC Paints' physical product offerings.

3. **Speed and Responsiveness**: Visualizations are generated within seconds to maintain customer engagement.

4. **Multi-Color Comparison**: Users can compare multiple color options side by side to facilitate decision making.

5. **Intuitive User Interface**: The clean, user-friendly design requires no technical expertise to operate.

6. **Environment Customization**: Room type and lighting condition settings ensure accurate visualizations across different contexts.

## Technical Components

- **Stable Diffusion**: Fine-tuned generative AI model for photorealistic room transformations
- **FastAPI Backend**: Handles image processing, visualization requests, and color catalog management
- **Image Processing Pipeline**: Standardizes and prepares images for visualization
- **Color Matching System**: Ensures digital color representations match physical paint products
- **Responsive Web Interface**: Provides an intuitive experience across desktop and mobile devices
- **LangChain Integration**: Orchestrates prompting and image generation workflows

## Limitations of the POC

- Visualization quality may vary based on the original image lighting and quality
- Limited wall detection capabilities compared to the full implementation
- Processing time increases with larger or more complex room images
- Color accuracy may require calibration on different display devices
- Comparison view currently limited to a defined number of colors

## Next Steps for Full Implementation

1. Enhanced wall detection using advanced computer vision techniques
2. Multi-wall color combinations for accent wall planning
3. Mobile application development for on-the-go visualization
4. E-commerce integration for direct paint ordering
5. Augmented reality capabilities for real-time room scanning
6. Advanced analytics to track visualization-to-purchase conversion