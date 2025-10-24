# Planning Game Theme - Chain of Thought Documentation

## Overview

The `planning_game_theme` tool implements a streamlined Chain of Thought (CoT) approach for game theme generation. It helps the game generator agent organize and plan game assets before implementation.

## Workflow

### Step 1: Search for Assets
Use `search_library()` to find candidate images:
```
search_library(query="platformer game assets", offset=0)
```

### Step 2: Plan Game Theme
Use `plan_game_theme()` to analyze and categorize the found assets:
```
plan_game_theme(
    candidate_images="url1,url2,url3",
    category="character",  # Optional: focus on specific category
    requirements="Create a platformer game"  # Optional: user requirements
)
```

### Step 3: Generate Game Code
Use the categorized assets to create game files:
```
write_game_file(folder_path="assets/images", file_name="bg.png", url="url1")
write_game_file(folder_path="", file_name="index.html", content="...")
```

## Asset Categories

The tool categorizes images into:
- **bg**: Background images
- **character**: Player/NPC sprites
- **obstacles**: Obstacles and enemies
- **ui**: UI elements and buttons
- **effects**: Visual effects (particles, explosions)
- **audio**: Sound effects and music

## Architecture

### PlanningGameTheme Class
Located in `graph/internal/helper/planning_game_theme.py`

**Key Methods:**
- `categorize_images()`: Analyzes image URLs and assigns categories
- `generate_game_theme()`: Creates a cohesive game theme from categorized assets
- `plan_game_theme()`: Complete workflow combining categorization and theme generation

**LLM Integration:**
- Uses lazy-loaded LLM model (default: gpt-4o-mini)
- Configurable temperature for creativity control
- Structured prompt engineering for consistent results

### Tool Wrapper
Located in `graph/internal/tools/planning_game_theme.py`

**Features:**
- LangChain tool integration
- Formatted output with categorized assets
- Gameplay suggestions based on available assets
- User-friendly error handling

## Integration

The tool is integrated into `game_generator_v1` workflow:

```python
async def get_toolset(self):
    return [
        init_or_load_game_source,
        write_game_file,
        build_source,
        search_library,
        plan_game_theme,  # <-- New tool
        web_search_tool,
    ]
```

## Benefits

1. **Organized Asset Management**: Automatically categorizes assets by purpose
2. **Theme Coherence**: Ensures assets work together thematically
3. **Gameplay Suggestions**: Provides actionable ideas based on available assets
4. **Reduced Iteration**: Fewer trial-and-error cycles in game development
5. **Streamlined Workflow**: Clear path from asset discovery to game implementation

## Example Usage

```python
# 1. Search for assets
results = search_library(query="space shooter sprites", offset=0)

# 2. Plan theme
theme = plan_game_theme(
    candidate_images="http://minio:9000/library/ship.png,http://minio:9000/library/stars.png",
    category="",
    requirements="Create a retro space shooter"
)

# Output:
# 🎮 Game Theme Plan
# ============================================================
# 📋 Theme: Retro Space Defender
# 
# A classic arcade-style space shooter with pixel art aesthetics...
# 
# ============================================================
# 🎨 Categorized Assets (2 total):
# 
# CHARACTER (1):
#   • http://minio:9000/library/ship.png - Player spaceship sprite
# 
# BG (1):
#   • http://minio:9000/library/stars.png - Starfield background
# 
# ============================================================
# 💡 Gameplay Suggestions:
# 1. Implement vertical scrolling shooter mechanics
# 2. Add enemy waves with increasing difficulty
# 3. Include power-up collectibles
```

## Future Enhancements

- Support for animated sprite analysis
- Asset quality assessment
- Style consistency checking
- Automatic game template selection
- Multi-language asset description support
