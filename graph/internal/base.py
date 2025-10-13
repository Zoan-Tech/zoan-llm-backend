from abc import ABC, abstractmethod
from prompt import BasePromptManager, langfuse_prompt_manager

class BaseInternalAgent(ABC):
    def __init__(
        self,
        prompt_manager: BasePromptManager = langfuse_prompt_manager,
    ):
        self.prompt_manager = prompt_manager
        
    @abstractmethod
    def get_prompt(self, **kwargs) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_agent(self, llm, system_prompt: str, **kwargs):
        raise NotImplementedError