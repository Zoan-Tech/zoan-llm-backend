from openai import AsyncOpenAI
from langgraph.prebuilt import create_react_agent
from prompt import BasePromptManager, langfuse_prompt_manager
from utils.enums import *
from utils.loop_runner import loop_runner

from config import Config
from config.logging import get_logger
from graph.internal.base import BaseInternalAgent

logger = get_logger()
    
class GameGenerator(BaseInternalAgent):
    PROMPT_GAME_GENERATOR_CONSTRUCTION = "Game Generator"
    SANITIZED_NAME = "game_generator"
        
    def get_prompt(self, **kwargs) -> str:
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_GAME_GENERATOR_CONSTRUCTION,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    async def _create_container(self):
        openai_client = AsyncOpenAI(
            api_key=Config.OPENAI_API_KEY,
        )
        
        container = await openai_client.containers.create(name="game-generator-container")
        return container

    
    async def get_toolset(self):
        container = await self._create_container()
        code_interpreter_tool = {
            "type": "code_interpreter",
            "container": container.id,
        }
        web_search_tool = {
            "type": "web_search"
        }
        return [code_interpreter_tool, web_search_tool]
    
    def get_agent(self, llm, system_prompt: str, **kwargs):
        toolset = loop_runner.run(self.get_toolset())  # <-- runs on dedicated loop thread
        return create_react_agent(
            model=llm,
            tools=list(toolset),
            prompt=system_prompt,
            name=self.SANITIZED_NAME,
        )
        
game_generator = GameGenerator()