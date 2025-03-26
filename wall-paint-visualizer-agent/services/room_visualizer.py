import os
import time
from PIL import Image
import numpy as np
from langchain.prompts import PromptTemplate

class RoomVisualizer:
    """
    Service for generating room visualizations with new paint colors
    """
    
    def __init__(self, model_id="timbrooks/instruct-pix2pix", use_auth_token=None):
        """
        Initialize the room visualizer
        
        Args:
            model_id: Hugging Face model ID for the text-to-image model
            use_auth_token: HuggingFace API token (if needed)
        """
        self.model_id = model_id
        
        # For POC, we'll just simulate model loading
        self.model = None
        self.device = "cpu"
        print(f"Using device: {self.device}")
        
        # For LangChain prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["room_type", "color_name", "hex_code", "color_family", "description", "lighting"],
            template="""
            Transform this room to have walls painted in {color_name} ({hex_code}), 
            which is a {color_family} color that {description}.
            This is a {room_type} with {lighting} conditions.
            Keep all furniture, decorations, and architectural elements exactly the same.
            Only change the wall color to {color_name}.
            Make the result photorealistic with accurate lighting.
            """
        )
    
    def _load_model(self):
        """Simulate loading the model"""
        if self.model is None:
            print(f"Loading model {self.model_id} on {self.device}...")
            
            # Simulate loading time
            time.sleep(2)
            print("Model loaded!")
    
    def visualize(self, image_path, color, room_type="living room", lighting="natural light", output_path=None):
        """
        Generate a visualization of a room with new paint color
        
        Args:
            image_path: Path to the room image
            color: Dictionary containing color information (name, hex_code, etc.)
            room_type: Type of room (e.g., living room, bedroom)
            lighting: Lighting condition description
            output_path: Path to save the output image
            
        Returns:
            Path to the generated visualization
        """
        try:
            # Simulate loading the model
            self._load_model()
            
            # Load the input image
            input_image = Image.open(image_path)
            
            # Generate the instruction prompt
            instruction = self.prompt_template.format(
                room_type=room_type,
                color_name=color["name"],
                hex_code=color["hex_code"],
                color_family=color["family"].lower(),
                description=color["description"].lower(),
                lighting=lighting
            )
            
            print(f"Generating visualization with instruction: {instruction}")
            
            # Simulate processing time
            time.sleep(3)
            
            # Apply a simple color overlay as a visual demonstration
            output_image = self._simulate_room_color_change(input_image, color["rgb"])
            
            # Save the output image
            if output_path is None:
                output_dir = "data/results"
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/visualization_{int(time.time())}.jpg"
            
            output_image.save(output_path)
            print(f"Visualization saved to {output_path}")
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Visualization failed: {str(e)}")
    
    def _simulate_room_color_change(self, image, rgb_color):
        """
        Simulated color change for POC purposes
        Handles images of different formats and dimensions
        """
        # Convert to numpy array
        img_array = np.array(image)
        
        # Check image dimensions and format
        if len(img_array.shape) == 2:
            # Convert grayscale to RGB
            img_array = np.stack((img_array,) * 3, axis=-1)
        elif len(img_array.shape) == 3 and img_array.shape[2] == 4:
            # Handle RGBA images by removing alpha channel
            img_array = img_array[:, :, :3]
        
        # Get image dimensions
        height, width, _ = img_array.shape
        
        # Create properly shaped color overlay
        color_layer = np.ones((height, width, 3), dtype=np.uint8)
        color_layer[:, :, 0] = rgb_color[0]
        color_layer[:, :, 1] = rgb_color[1]
        color_layer[:, :, 2] = rgb_color[2]
        
        # Apply blending with controlled strength
        tint_strength = 0.3  # How strong the tint effect is
        blended = img_array * (1 - tint_strength) + color_layer * tint_strength
        blended = np.clip(blended, 0, 255).astype(np.uint8)
        
        # Convert back to PIL Image
        output_image = Image.fromarray(blended)
        
        return output_image
    
    def compare_colors(self, image_path, colors, room_type="living room", lighting="natural light"):
        """
        Generate visualizations for multiple colors for comparison
        
        Args:
            image_path: Path to the room image
            colors: List of color dictionaries
            room_type: Type of room
            lighting: Lighting condition description
            
        Returns:
            List of paths to the generated visualizations
        """
        result_paths = []
        
        for color in colors:
            output_path = self.visualize(
                image_path=image_path,
                color=color,
                room_type=room_type,
                lighting=lighting
            )
            result_paths.append(output_path)
        
        return result_paths