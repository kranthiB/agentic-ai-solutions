from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import shutil
import os
from typing import List
import uuid
from datetime import datetime
from pydantic import BaseModel
import asyncio

# Import services
from services.image_processor import ImageProcessor
from services.paint_catalog import PaintCatalog
from services.room_visualizer import RoomVisualizer

app = FastAPI(title="Paints Room Visualizer API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
paint_catalog = PaintCatalog()
image_processor = ImageProcessor()
room_visualizer = RoomVisualizer()

# Create upload directory
os.makedirs("data/uploads", exist_ok=True)
os.makedirs("data/results", exist_ok=True)

class VisualizationRequest(BaseModel):
    image_id: str
    paint_color_id: str
    room_type: str = "living room"
    lighting_condition: str = "natural light"

@app.get("/")
def read_root():
    return {"message": "Paints Room Visualizer API"}

@app.get("/colors")
def get_colors():
    """Get all available paint colors"""
    return paint_catalog.get_all_colors()

@app.get("/colors/{color_id}")
def get_color(color_id: str):
    """Get specific paint color details"""
    color = paint_catalog.get_color_by_id(color_id)
    if not color:
        raise HTTPException(status_code=404, detail="Color not found")
    return color

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload a room image"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique ID for the image
    image_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{image_id}_{timestamp}{os.path.splitext(file.filename)[1]}"
    
    # Save the uploaded file
    file_path = f"data/uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Process the image to prepare it for visualization
    processed_image_path = image_processor.process_image(file_path)
    
    return {
        "image_id": image_id,
        "filename": filename,
        "original_path": file_path,
        "processed_path": processed_image_path
    }

@app.post("/visualize")
async def visualize_room(request: VisualizationRequest):
    """Generate visualization of room with selected paint color"""
    # Get color details
    color = paint_catalog.get_color_by_id(request.paint_color_id)
    if not color:
        raise HTTPException(status_code=404, detail="Color not found")
    
    # Find the uploaded image
    image_files = [f for f in os.listdir("data/uploads") if f.startswith(request.image_id)]
    if not image_files:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image_path = f"data/uploads/{image_files[0]}"
    
    # Generate visualization
    result_id = str(uuid.uuid4())
    result_path = f"data/results/{result_id}.jpg"
    
    try:
        # This might take some time, so we'll make it non-blocking
        # For a real implementation, consider using background tasks or a queue
        await asyncio.to_thread(
            room_visualizer.visualize,
            image_path=image_path,
            color=color,
            room_type=request.room_type,
            lighting=request.lighting_condition,
            output_path=result_path
        )
        
        return {
            "visualization_id": result_id,
            "color": color,
            "image_id": request.image_id,
            "result_path": result_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization failed: {str(e)}")

@app.get("/results/{visualization_id}")
def get_visualization(visualization_id: str):
    """Get a generated visualization"""
    result_path = f"data/results/{visualization_id}.jpg"
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Visualization not found")
    
    return FileResponse(result_path)

@app.get("/compare")
def compare_visualizations(visualization_ids: List[str]):
    """Get multiple visualizations for comparison"""
    results = []
    for viz_id in visualization_ids:
        result_path = f"data/results/{viz_id}.jpg"
        if os.path.exists(result_path):
            results.append({
                "visualization_id": viz_id,
                "result_path": result_path
            })
    
    if not results:
        raise HTTPException(status_code=404, detail="No visualizations found")
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)