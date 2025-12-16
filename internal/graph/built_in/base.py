from abc import ABC, abstractmethod
from internal.graph.builder.prompt import BasePromptManager, langfuse_prompt_manager
from model import AgentConfig
from config import Config
from langchain.chat_models import init_chat_model
from langgraph_swarm import create_handoff_tool

PRIMARY_AGENT_NAME = "supervisor"

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
        
    def _prepare_handoff_tools(self, is_primary: bool = False, agent_names: list[str] = []) -> list:
        if is_primary:
            self.handoff_tools = [
                create_handoff_tool(
                    agent_name=agent_name,
                    name=f"zoan_internal_handoff_to_{agent_name}",
                    description=f"Transfer control to agent '{agent_name}' to handle user corresponding requests"
                ) for agent_name in agent_names if agent_name != PRIMARY_AGENT_NAME
            ]
        else:
            self.handoff_tools = [
                create_handoff_tool(
                    agent_name=PRIMARY_AGENT_NAME,
                    name=f"zoan_internal_handoff_to_{PRIMARY_AGENT_NAME}",
                    description="Complete current task, return control to the primary agent"
                )
            ]