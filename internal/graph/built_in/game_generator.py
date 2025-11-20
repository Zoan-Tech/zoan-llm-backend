from typing import Optional
from langchain.agents import create_agent

from config import Config
from config.logging import get_logger
from internal.graph.built_in.base import BaseInternalAgent
from internal.graph.built_in.tools.game_generator import (
    search_knowledge_hub,
    init_or_load_game_source,
    read_source_structure,
    read_file,
    str_replace_editor,
    write_game_file,
    build_source,
    clean_up,
)

from internal.graph.built_in.middleware.base import get_base_middleware

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
    
    def _get_provider_built_in_tool(self, provider: Optional[str] = None):
        if provider == "openai":
            return [
                {"type": "web_search"}
            ]
        elif provider == "anthropic":
            return [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            }]
        else:
            return []
    
    async def get_toolset(self, provider: Optional[str] = None):
        """Get the tools available for game generation"""
        built_in_tools = self._get_provider_built_in_tool(provider)
        
        base_tools = [
            search_knowledge_hub,
            init_or_load_game_source,
            read_source_structure,
            read_file,
            str_replace_editor,
            write_game_file,
            build_source,
            clean_up,
        ]
        
        base_tools.extend(built_in_tools)
        return base_tools
    
    def get_middleware(self) -> list:
        base_middleware = get_base_middleware()
        
        return base_middleware
    
    def get_agent(self, llm, system_prompt: str, **kwargs):
        """Create the agent with the LLM and tools"""
        from utils.loop_runner import loop_runner
        provider = kwargs.get("provider", None)

        toolset = loop_runner.run(self.get_toolset(provider))
        middleware = self.get_middleware()
        
        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )


game_generator_v1 = GameGeneratorV1()
