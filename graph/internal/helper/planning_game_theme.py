"""
Planning Game Theme Helper

This module provides functionality to plan game themes based on candidate images.
It uses LLM to analyze images and categorize them into different game asset types
(background, character, obstacles, etc.) and generate coherent game themes.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from config import Config
from config.logging import get_logger

logger = get_logger()


class ImageCategory(BaseModel):
    """Represents a categorized image with its purpose"""
    url: str = Field(description="URL of the image")
    category: str = Field(description="Category/purpose of the image (e.g., bg, character, obstacles, ui)")
    description: str = Field(default="", description="Brief description of the image")


class GameTheme(BaseModel):
    """Represents a game theme with categorized assets"""
    theme_name: str = Field(description="Name of the game theme")
    theme_description: str = Field(description="Description of the game theme")
    categorized_images: List[ImageCategory] = Field(default_factory=list, description="Images categorized by purpose")
    gameplay_suggestions: List[str] = Field(default_factory=list, description="Gameplay mechanic suggestions")


class PlanningGameTheme:
    """
    A class that uses LLM to analyze candidate images and plan game themes.
    
    This class segments images into categories (bg, character, obstacles, etc.)
    and generates cohesive game theme suggestions based on the available assets.
    """
    
    DEFAULT_CATEGORIES = ["bg", "character", "obstacles", "ui", "effects", "audio"]
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.7):
        """
        Initialize the PlanningGameTheme with an LLM model.
        
        Args:
            model_name: The LLM model to use for planning
            temperature: Temperature parameter for the LLM
        """
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
        
    @property
    def llm(self):
        """Lazy load the LLM model"""
        if self._llm is None:
            self._llm = init_chat_model(
                model=self.model_name,
                temperature=self.temperature,
                timeout=60,
            )
        return self._llm
    
    def categorize_images(
        self, 
        candidate_images: List[str], 
        expected_category: Optional[str] = None
    ) -> List[ImageCategory]:
        """
        Categorize candidate images into different asset types.
        
        Args:
            candidate_images: List of image URLs to categorize
            expected_category: Optional specific category to focus on
            
        Returns:
            List of ImageCategory objects with categorized images
        """
        if not candidate_images:
            logger.warning("[PlanningGameTheme] No candidate images provided for categorization")
            return []
        
        try:
            # Build the prompt for categorization
            category_filter = f" focusing on '{expected_category}' category" if expected_category else ""
            prompt = f"""Analyze these game asset image URLs{category_filter} and categorize them:

Images:
{chr(10).join(f"- {url}" for url in candidate_images)}

Available categories: {', '.join(self.DEFAULT_CATEGORIES)}

For each image, provide:
1. The most appropriate category (from the list above)
2. A brief description of what the image contains

Format your response as:
URL: <image_url>
Category: <category>
Description: <description>

---

Analyze all images and provide categorization."""

            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the response to extract categorizations
            categorized = self._parse_categorization_response(content, candidate_images)
            
            logger.info(f"[PlanningGameTheme] Categorized {len(categorized)} images")
            return categorized
            
        except Exception as e:
            logger.error(f"[PlanningGameTheme] Error categorizing images: {e}")
            # Fallback: return uncategorized images
            return [
                ImageCategory(url=url, category="unknown", description="")
                for url in candidate_images
            ]
    
    def _parse_categorization_response(
        self, 
        response_content: str, 
        candidate_images: List[str]
    ) -> List[ImageCategory]:
        """Parse LLM response to extract image categorizations"""
        categorized = []
        
        # Split response into blocks separated by ---
        blocks = response_content.split('---')
        
        for block in blocks:
            lines = block.strip().split('\n')
            url, category, description = None, None, ""
            
            for line in lines:
                line = line.strip()
                if line.startswith('URL:'):
                    url = line.replace('URL:', '').strip()
                elif line.startswith('Category:'):
                    category = line.replace('Category:', '').strip().lower()
                elif line.startswith('Description:'):
                    description = line.replace('Description:', '').strip()
            
            if url and category:
                # Validate URL is in candidate_images
                if url in candidate_images:
                    categorized.append(ImageCategory(
                        url=url,
                        category=category,
                        description=description
                    ))
        
        # If parsing failed, try to match any URLs found
        if not categorized:
            for url in candidate_images:
                if url in response_content:
                    categorized.append(ImageCategory(
                        url=url,
                        category="general",
                        description=""
                    ))
        
        return categorized
    
    def generate_game_theme(
        self, 
        categorized_images: List[ImageCategory],
        user_requirements: Optional[str] = None
    ) -> GameTheme:
        """
        Generate a cohesive game theme based on categorized images.
        
        Args:
            categorized_images: List of categorized images
            user_requirements: Optional user requirements or preferences
            
        Returns:
            GameTheme object with theme details and suggestions
        """
        if not categorized_images:
            logger.warning("[PlanningGameTheme] No categorized images provided for theme generation")
            return GameTheme(
                theme_name="Generic Game",
                theme_description="A basic game without specific theme",
                categorized_images=[],
                gameplay_suggestions=[]
            )
        
        try:
            # Build prompt for theme generation
            images_by_category = {}
            for img in categorized_images:
                if img.category not in images_by_category:
                    images_by_category[img.category] = []
                images_by_category[img.category].append(f"{img.url} ({img.description})")
            
            category_summary = "\n".join([
                f"- {cat}: {len(imgs)} image(s)"
                for cat, imgs in images_by_category.items()
            ])
            
            user_req_section = f"\n\nUser Requirements:\n{user_requirements}" if user_requirements else ""
            
            prompt = f"""Based on these categorized game assets, create a cohesive game theme:

Available Assets:
{category_summary}
{user_req_section}

Provide:
1. A creative game theme name
2. A detailed theme description
3. Gameplay mechanic suggestions that work with the available assets

Format your response as:
Theme Name: <name>
Theme Description: <description>
Gameplay Suggestions:
- <suggestion 1>
- <suggestion 2>
- <suggestion 3>
"""

            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the theme response
            theme = self._parse_theme_response(content, categorized_images)
            
            logger.info(f"[PlanningGameTheme] Generated theme: {theme.theme_name}")
            return theme
            
        except Exception as e:
            logger.error(f"[PlanningGameTheme] Error generating game theme: {e}")
            return GameTheme(
                theme_name="Game Theme",
                theme_description="A game based on available assets",
                categorized_images=categorized_images,
                gameplay_suggestions=["Use available assets creatively"]
            )
    
    def _parse_theme_response(
        self, 
        response_content: str, 
        categorized_images: List[ImageCategory]
    ) -> GameTheme:
        """Parse LLM response to extract game theme details"""
        lines = response_content.strip().split('\n')
        
        theme_name = "Game Theme"
        theme_description = ""
        gameplay_suggestions = []
        
        in_suggestions = False
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('Theme Name:'):
                theme_name = line.replace('Theme Name:', '').strip()
            elif line.startswith('Theme Description:'):
                theme_description = line.replace('Theme Description:', '').strip()
            elif line.startswith('Gameplay Suggestions:'):
                in_suggestions = True
            elif in_suggestions and line.startswith('-'):
                suggestion = line.lstrip('-').strip()
                if suggestion:
                    gameplay_suggestions.append(suggestion)
            elif in_suggestions and not line:
                in_suggestions = False
        
        return GameTheme(
            theme_name=theme_name,
            theme_description=theme_description,
            categorized_images=categorized_images,
            gameplay_suggestions=gameplay_suggestions
        )
    
    def plan_game_theme(
        self,
        candidate_images: List[str],
        expected_category: Optional[str] = None,
        user_requirements: Optional[str] = None
    ) -> GameTheme:
        """
        Complete workflow: categorize images and generate game theme.
        
        Args:
            candidate_images: List of image URLs to analyze
            expected_category: Optional specific category to focus on
            user_requirements: Optional user requirements or preferences
            
        Returns:
            GameTheme object with complete theme planning
        """
        logger.info(f"[PlanningGameTheme] Planning game theme for {len(candidate_images)} images")
        
        # Step 1: Categorize images
        categorized = self.categorize_images(candidate_images, expected_category)
        
        # Step 2: Generate theme
        theme = self.generate_game_theme(categorized, user_requirements)
        
        return theme


# Singleton instance
planning_game_theme = PlanningGameTheme()
