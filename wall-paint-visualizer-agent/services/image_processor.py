from PIL import Image
import os
import numpy as np

class ImageProcessor:
    """
    Service for processing room images before visualization
    """
    
    def __init__(self):
        """Initialize the image processor service"""
        # Create directory for processed images
        os.makedirs("data/processed", exist_ok=True)
    
    def process_image(self, image_path: str) -> str:
        """
        Process an uploaded image to prepare it for visualization
        
        Args:
            image_path: Path to the original uploaded image
            
        Returns:
            Path to the processed image
        """
        try:
            # Open the image
            img = Image.open(image_path)
            
            # Standardize image size - resizing to a width of 1024px
            # while maintaining aspect ratio
            base_width = 1024
            w_percent = base_width / float(img.size[0])
            h_size = int(float(img.size[1]) * float(w_percent))
            img = img.resize((base_width, h_size), Image.LANCZOS)
            
            # Ensure RGB mode (convert if needed)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Save the processed image
            processed_name = f"processed_{os.path.basename(image_path)}"
            processed_path = f"data/processed/{processed_name}"
            img.save(processed_path, quality=90)
            
            return processed_path
            
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")
    
    def enhance_image(self, image_path: str) -> str:
        """
        Enhance image quality for better visualization results
        
        Args:
            image_path: Path to the image to enhance
            
        Returns:
            Path to the enhanced image
        """
        try:
            # Open the image
            img = Image.open(image_path)
            
            # Basic enhancements for demonstration
            # In a production system, you might use more sophisticated techniques
            
            # Convert to numpy array for processing
            img_array = np.array(img)
            
            # Simple contrast enhancement
            # Using a basic linear mapping to stretch the histogram
            p5 = np.percentile(img_array, 5)
            p95 = np.percentile(img_array, 95)
            
            if p95 > p5:
                img_array = np.clip((img_array - p5) * (255.0 / (p95 - p5)), 0, 255).astype(np.uint8)
            
            # Convert back to PIL image
            enhanced_img = Image.fromarray(img_array)
            
            # Save the enhanced image
            enhanced_name = f"enhanced_{os.path.basename(image_path)}"
            enhanced_path = f"data/processed/{enhanced_name}"
            enhanced_img.save(enhanced_path, quality=95)
            
            return enhanced_path
            
        except Exception as e:
            # If enhancement fails, return the original image
            print(f"Enhancement warning: {str(e)}")
            return image_path
    
    def analyze_room(self, image_path: str) -> dict:
        """
        Analyze room characteristics to guide visualization
        
        Args:
            image_path: Path to the room image
            
        Returns:
            Dictionary with room analysis results
        """
        # This is a simplified mock implementation
        # In a real system, this would use computer vision to detect walls,
        # lighting conditions, furniture, etc.
        
        # For POC purposes, we'll return some mock analysis
        return {
            "detected_walls": True,
            "wall_area_percentage": 65,
            "room_brightness": "medium",
            "dominant_colors": ["#E8E5DE", "#8A8C8F", "#4D4E50"],
            "estimated_room_type": "living room",
        }


if __name__ == "__main__":
    # Test the image processor
    processor = ImageProcessor()
    
    # This would fail in testing unless you have this file
    # test_image_path = "data/test_image.jpg"
    # if os.path.exists(test_image_path):
    #     processed_path = processor.process_image(test_image_path)
    #     print(f"Processed image saved to: {processed_path}")
    #
    #     enhanced_path = processor.enhance_image(processed_path)
    #     print(f"Enhanced image saved to: {enhanced_path}")
    #
    #     analysis = processor.analyze_room(processed_path)
    #     print(f"Room analysis: {analysis}")