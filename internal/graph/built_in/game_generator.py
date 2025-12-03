from typing import Optional
from langchain.agents import create_agent

from config import Config
from config.logging import get_logger
from internal.graph.built_in.base import BaseInternalAgent
from internal.graph.built_in.tools.base import ProviderBuiltInTool, BuiltinToolName

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
from model import AgentConfig
from internal.graph.built_in.middleware.base import get_base_middleware
from internal.graph.builder.agent import AgentBuilder

logger = get_logger()

class GameGeneratorV1(BaseInternalAgent):
    """
    Game Generator V1 - Local HTML/CSS/JS Game Builder
    
    This version generates games locally using HTML/CSS/JS without code interpreter.
    It manages game versions, downloads assets, debugs locally, and uploads to MinIO.
    """
    SANITIZED_NAME = "game_generator"
    PROMPT_NAME = "game_generator_v1"
    
    def _get_provider_built_in_tool(self, model: str = None):
        if "openai" in model:
            return [ProviderBuiltInTool.OPENAI.values()]
        elif "anthropic" in model:
            return [ProviderBuiltInTool.ANTHROPIC.values()]
        else:
            return []
    
    def get_toolset(self, model: str):
        """Get the tools available for game generation"""
        built_in_tools = self._get_provider_built_in_tool(model)
        
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
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        """Create the agent with the LLM and tools"""
        llm = AgentBuilder._construct_llm_model(agent_config)
        
        toolset = self.get_toolset(agent_config.model)
        
        system_prompt = self.get_prompt()
        middleware = self.get_middleware()
        
        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )


game_generator_v1 = GameGeneratorV1()
