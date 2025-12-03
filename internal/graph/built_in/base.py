from abc import ABC, abstractmethod
from internal.graph.builder.prompt import BasePromptManager, langfuse_prompt_manager
from model import AgentConfig
from config import Config
from langchain.chat_models import init_chat_model

class BaseInternalAgent(ABC):
    PROMPT_NAME = ""
    
    def __init__(
        self,
        prompt_manager: BasePromptManager = langfuse_prompt_manager,
    ):
        self.prompt_manager = prompt_manager
        
    def get_prompt(self, **kwargs) -> str:
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_NAME,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    @abstractmethod
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        raise NotImplementedError
    
    def _construct_llm_model(self, agent_config: AgentConfig):
        return init_chat_model(
            model=agent_config.model,
            stream_usage=agent_config.stream_usage,
            timeout=120,
            max_retries=2,
            **agent_config.model_kwargs.model_dump(),
        )