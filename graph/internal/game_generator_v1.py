from langgraph.prebuilt import create_react_agent

from config import Config
from config.logging import get_logger
from graph.internal.base import BaseInternalAgent
from graph.internal.tools.game_generator_v1 import (
    init_or_load_game_source,
    write_game_file,
    debug_source,
    build_source,
)
from graph.internal.tools.game_generator import search_library

logger = get_logger()


class GameGeneratorV1(BaseInternalAgent):
    """
    Game Generator V1 - Local HTML/CSS/JS Game Builder
    
    This version generates games locally using HTML/CSS/JS without code interpreter.
    It manages game versions, downloads assets, debugs locally, and uploads to MinIO.
    """
    SANITIZED_NAME = "game_generator"
    PROMPT_GAME_GENERATOR_CONSTRUCTION = "game_generator_v1"
    
    def get_prompt(self, **kwargs) -> str:
        """Get the system prompt for the game generator"""
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_GAME_GENERATOR_CONSTRUCTION,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    async def get_toolset(self):
        """Get the tools available for game generation"""
        web_search_tool = {
            "type": "web_search"
        }
        return [
            init_or_load_game_source,
            write_game_file,
            # debug_source,
            build_source,
            search_library,
            web_search_tool,
        ]
    
    def get_agent(self, llm, system_prompt: str, **kwargs):
        """Create the agent with the LLM and tools"""
        from utils.loop_runner import loop_runner
        
        toolset = loop_runner.run(self.get_toolset())
        return create_react_agent(
            model=llm,
            tools=list(toolset),
            prompt=system_prompt,
            name=self.SANITIZED_NAME,
        )


game_generator_v1 = GameGeneratorV1()
