from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.tools.base import search_knowledge_base, read_url
from internal.agent.tools.game_generator import (
    init_or_load_game_source,
    read_source_structure,
    read_file,
    str_replace_editor,
    write_game_file,
    build_source,
    clean_up,
)
from model.completion import AgentConfig
from internal.agent.middleware.base import get_base_middleware
from internal.builder.agent import AgentBuilder
from langchain.agents.middleware import TodoListMiddleware

logger = get_logger()

class GameGeneratorV1(BaseInternalAgent):
    """
    Game Generator V1 - Local HTML/CSS/JS Game Builder
    
    This version generates games locally using HTML/CSS/JS without code interpreter.
    It manages game versions, downloads assets, debugs locally, and uploads to MinIO.
    """
    SANITIZED_NAME = "game_generator"
    PROMPT_NAME = "game_generator_v1"
    
    def get_toolset(self, model: str):
        """Get the tools available for game generation"""
        
        base_tools = [
            search_knowledge_base,
            read_url,
            init_or_load_game_source,
            read_source_structure,
            read_file,
            str_replace_editor,
            write_game_file,
            build_source,
            clean_up,
        ]
        
        return base_tools + self.handoff_tools
    
    def get_middleware(self) -> list:
        base_middleware = get_base_middleware()
        middlewares = [
            TodoListMiddleware(),
        ]
        
        return middlewares
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        """Create the agent with the LLM and tools"""
        self._prepare_handoff_tools(agent_config.is_primary)
        llm = AgentBuilder._construct_llm_model(agent_config)
        
        toolset = self.get_toolset(agent_config.model)
        
        system_prompt = self.get_prompt()
        with open("prompt_draft/game_generator_prompt_draft.md", "r") as f:
            system_prompt = f.read()
            
        middleware = self.get_middleware()
        
        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )


game_generator_v1 = GameGeneratorV1()
