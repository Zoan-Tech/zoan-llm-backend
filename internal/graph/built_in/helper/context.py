"""
Image injection helper for primary agent.
Injects images from tool results into the message history for visual analysis.
"""
import base64
import json
import mimetypes
from typing import Any, Dict

import httpx
from langchain_core.messages import HumanMessage, ToolMessage

from config.logging import get_logger

logger = get_logger()

def inject_images_from_tool_results(messages: list, existing_urls: list = []) -> Dict[str, Any]:
    """
    Graph node that injects images from tool results into the message history.
    
    This should be used as a separate node AFTER the tool node in the graph,
    not as a post_model_hook, to avoid breaking Anthropic's tool message ordering.
    
    This function:
    1. Scans recent ToolMessages for image URLs
    2. Downloads and base64 encodes the images
    3. Injects them as HumanMessage with image content blocks
    
    Args:
        state: The current graph state with messages
        
    Returns:
        State update with injected image messages (if any)
    """
    # Look for recent ToolMessages with image_urls
    new_messages = []
    new_images = []
    all_image_urls = []  # Changed from set to list
    MAX_IMAGES = 10
    
    # Only look at the most recent messages to find tool results
    for message in messages[::-1]:  # Reverse order
        content = message.content
        if isinstance(content, str):
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                data = {}
        elif isinstance(content, dict):
            data = content
        else:
            continue
        
        # Check if this tool result has image URLs
        image_urls_list = data.get("image_urls", [])
        if isinstance(image_urls_list, list):
            all_image_urls.extend(image_urls_list)  # Extend list with images
    
    # Inject images (limit to MAX_IMAGES to avoid token overload)
    for img_data in all_image_urls:
        if len(new_messages) >= MAX_IMAGES:
            break
        
        # Handle both dict and string formats
        if isinstance(img_data, dict):
            img_url = img_data.get("url")
        elif isinstance(img_data, str):
            img_url = img_data
        else:
            continue
        
        if not img_url:
            continue
        if img_url in existing_urls or img_url in new_images:
            continue
        
        try:
            # Download and encode image
            response = httpx.get(img_url, timeout=10.0)
            response.raise_for_status()
            
            encoded_image = base64.b64encode(response.content).decode("utf-8")  # Fixed variable name
            
            mime_type, _ = mimetypes.guess_type(img_url)
            
            # Create image message
            img_msg = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"📸 Image context: {img_url}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }
                    }
                ]
            )
            
            new_messages.append(img_msg)
            new_images.append(img_url)
            
        except Exception as e:
            continue
    
    # Return state update with new messages if any were created
    if len(new_messages) > 0:
        return {
            "messages": new_messages,
            "images": new_images,
        }
    
    return {}
