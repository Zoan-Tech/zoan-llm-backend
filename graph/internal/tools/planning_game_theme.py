"""
Planning Game Theme Tool

A LangChain tool that wraps the PlanningGameTheme helper to provide
game theme planning capabilities based on candidate images.
"""

from typing import Annotated, Optional
from langchain_core.tools import tool

from config.logging import get_logger
from graph.internal.helper.planning_game_theme import planning_game_theme

logger = get_logger()


@tool
def plan_game_theme(
    candidate_images: Annotated[str, "Comma-separated list of candidate image URLs from search_library"],
    category: Annotated[Optional[str], "Expected category/purpose for the images (e.g., 'bg', 'character', 'obstacles'). Leave empty to categorize all."] = None,
    requirements: Annotated[Optional[str], "User requirements or preferences for the game theme"] = None,
) -> str:
    """
    Plan a game theme by analyzing and categorizing candidate images from the library.
    
    This tool helps you:
    1. Categorize candidate images into asset types (background, character, obstacles, UI, effects, audio)
    2. Generate a cohesive game theme based on available assets
    3. Get gameplay mechanic suggestions
    
    Usage:
    - After using search_library() to find assets, use this tool to plan the game theme
    - Provide the image URLs (comma-separated) from search results
    - Optionally specify a category to focus on (e.g., 'character' to find character assets)
    - Optionally provide user requirements to guide theme generation
    
    Examples:
    - plan_game_theme(candidate_images="http://minio:9000/library/bg1.png,http://minio:9000/library/char1.png", category="", requirements="Create a platformer game")
    - plan_game_theme(candidate_images="http://minio:9000/library/sprite1.png,http://minio:9000/library/sprite2.png", category="character", requirements="")
    
    Returns a formatted string with:
    - Theme name and description
    - Categorized assets by type
    - Gameplay suggestions
    """
    try:
        # Parse comma-separated URLs
        image_urls = [url.strip() for url in candidate_images.split(',') if url.strip()]
        
        if not image_urls:
            return "❌ No valid image URLs provided. Use search_library() to find assets first."
        
        logger.info(f"[plan_game_theme] Planning theme for {len(image_urls)} images with category='{category}'")
        
        # Use the planning helper to generate theme
        theme = planning_game_theme.plan_game_theme(
            candidate_images=image_urls,
            expected_category=category if category else None,
            user_requirements=requirements if requirements else None
        )
        
        # Format the response
        result_parts = [
            f"🎮 Game Theme Plan",
            f"\n{'='*60}\n",
            f"📋 Theme: {theme.theme_name}",
            f"\n{theme.theme_description}\n",
            f"\n{'='*60}\n",
            f"🎨 Categorized Assets ({len(theme.categorized_images)} total):\n"
        ]
        
        # Group by category
        by_category = {}
        for img in theme.categorized_images:
            if img.category not in by_category:
                by_category[img.category] = []
            by_category[img.category].append(img)
        
        for cat, images in by_category.items():
            result_parts.append(f"\n{cat.upper()} ({len(images)}):")
            for img in images:
                desc = f" - {img.description}" if img.description else ""
                result_parts.append(f"  • {img.url}{desc}")
        
        # Add gameplay suggestions
        if theme.gameplay_suggestions:
            result_parts.append(f"\n\n{'='*60}\n")
            result_parts.append("💡 Gameplay Suggestions:\n")
            for i, suggestion in enumerate(theme.gameplay_suggestions, 1):
                result_parts.append(f"{i}. {suggestion}")
        
        result_parts.append(f"\n\n{'='*60}\n")
        result_parts.append("✅ Theme planning complete! Use write_game_file() to download and integrate these assets.")
        
        return "".join(result_parts)
        
    except Exception as e:
        logger.error(f"[plan_game_theme] Error: {e}")
        return f"❌ Error planning game theme: {str(e)}"
