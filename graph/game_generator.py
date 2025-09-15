from langgraph.prebuilt import create_react_agent
from prompt import BasePromptManager, DEFAULT_PROMPT_MANAGER
from action.minio_game_builder import MinioGameBuilder, DEFAULT_MINIO_GAME_BUILDER
import os
from utils.enums import *
from config.logging import get_logger

logger = get_logger()
game_builder: MinioGameBuilder = DEFAULT_MINIO_GAME_BUILDER
    
class GameGenerator:
    PROMPT_GAME_GENERATOR_CONSTRUCTION = "Game Generator"
    SANTIZED_NAME = "game_generator"
    
    def __init__(
        self,
        prompt_manager: BasePromptManager = DEFAULT_PROMPT_MANAGER,
    ):
        self.prompt_manager = prompt_manager
        
    def get_game_generation_prompt(self, **kwargs) -> str:
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_GAME_GENERATOR_CONSTRUCTION,
            label=os.getenv(SecretEnum.LANGFUSE_PROMPT_LABEL.value),
            version=os.getenv(SecretEnum.LANGFUSE_VERSION_ID.value),
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    def get_toolset(self):
        code_interpreter_tool = {
            "type": "code_interpreter",
            "container": {"type": "auto"},
        }
        return [code_interpreter_tool]
    
    def get_llm(self):
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model="gpt-5",
            api_key=os.environ.get("OPENAI_API_KEY"),
            max_tokens=20000,
            stream_usage=True,
            reasoning={
                "effort": "low",  # can be "low", "medium", or "high"
                "summary": "auto",  # can be "auto", "concise", or "detailed"
            },
            use_responses_api=True,
        )
    
    def get_generator(self):
        return create_react_agent(
            model=self.get_llm(),
            tools=self.get_toolset(),
            prompt=self.get_game_generation_prompt(),
            name=self.SANTIZED_NAME
        )
        
DEFAULT_GAME_GENERATOR = GameGenerator()