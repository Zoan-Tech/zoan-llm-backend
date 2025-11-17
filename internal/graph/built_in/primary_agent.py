from langchain.agents import create_agent

from config import Config
from internal.graph.built_in.base import BaseInternalAgent
from internal.graph.built_in.tools.primary_agent import (
    zoan_internal_update_chat_title,
)
from internal.graph.built_in.middleware.base import get_base_middleware

class PrimaryAgent(BaseInternalAgent):
    SANITIZED_NAME = "supervisor"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "primary_agent_v1"
    
    def get_prompt(self, **kwargs) -> str:
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_PRIMARY_AGENT_CONSTRUCTION,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    def get_toolset(self, custom_handoff_tools: list = []) -> list:
        internal_tools = [
            zoan_internal_update_chat_title,
        ]
        
        return internal_tools + custom_handoff_tools
    
    def get_middleware(self) -> list:
        base_middleware = get_base_middleware()
        return base_middleware
    
    def get_agent(self, llm, system_prompt: str, **kwargs):
        toolset = self.get_toolset(custom_handoff_tools=kwargs.get("custom_handoff_tools", []))
        middleware = self.get_middleware()

        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )
        
primary_agent = PrimaryAgent()