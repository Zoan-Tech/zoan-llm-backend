"""
Game Theme Planning Helper

This module provides AI-powered game theme planning capabilities that analyze
candidate images and generate focused game theme recommendations.
"""

import base64, httpx
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model

from utils.model import Model
from config.logging import get_logger

logger = get_logger()


MAX_TOKENS = 3000
class GameThemePlanner:
    """
    AI-powered game theme planner that analyzes candidate images and generates
    focused theme recommendations with maximum 2 themes per analysis.
    """
    
    def __init__(self, model: str = Model.openai_gpt_5_mini, max_tokens: int = MAX_TOKENS, **kwargs):
        """Initialize the theme planner with LLM configuration."""
        self.llm = init_chat_model(
            model=model,
            max_tokens=max_tokens,
            **kwargs
        )
        
    def _prepare_input_messages(self, prompt: str, images: List[str]) -> List[HumanMessage]:
        content = [
            {"type": "text", "text": (
                "Start processing these following assets.\n"
            )}
        ]
        
        for image_url in images:
            image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_data}"
                },
            })
        
        return [SystemMessage(content=prompt), HumanMessage(content=content)]
        
    def analyze_comprehensive(self, candidate_images: List[str], game_requirements: str) -> Dict[str, Any]:
        """
        Perform comprehensive analysis across all categories.
        Returns maximum 2 comprehensive themes with asset breakdowns.
        """
        planning_prompt = f"""
Based on the categorized image analyses and user requirements, create EXACTLY 2 distinct comprehensive game themes:

USER REQUIREMENTS:
{game_requirements or "No specific requirements provided"}

Please provide EXACTLY 2 distinct game theme concepts in this format:

**THEME 1: [Theme Name]**
- **Description**: [3-4 sentence description of the complete game concept, mood, and style]
- **Selected Assets by Category**:
  - **[Category]**: [Asset URL] - [Role in game]
  - **[Category]**: [Asset URL] - [Role in game]
  - (Continue for each category with assets)
- **Game Mechanics**: [Core gameplay mechanics that fit this theme]
- **Missing Assets**: [Key additional assets needed for this theme]

**THEME 2: [Theme Name]**
- **Description**: [3-4 sentence description of the complete game concept, mood, and style]
- **Selected Assets by Category**:
  - **[Category]**: [Asset URL] - [Role in game]
  - **[Category]**: [Asset URL] - [Role in game]
  - (Continue for each category with assets)
- **Game Mechanics**: [Core gameplay mechanics that fit this theme]
- **Missing Assets**: [Key additional assets needed for this theme]

Make the themes distinct and ensure each uses different combinations of the available assets across categories.
"""
        input_messages = self._prepare_input_messages(planning_prompt, candidate_images)
        theme_response = self.llm.invoke(input_messages)
        
        return theme_response.content


# Create a singleton instance for easy access
game_theme_planner = GameThemePlanner()
