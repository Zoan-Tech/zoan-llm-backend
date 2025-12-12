from langchain.agents import create_agent

from internal.graph.built_in.base import BaseInternalAgent
from internal.graph.built_in.tools.base import ProviderBuiltInTool, BuiltinToolName
from internal.graph.built_in.tools.primary_agent import (
    zoan_internal_update_chat_title,
    zoan_internal_search_uploaded_documents,
)
from model import AgentConfig
from internal.graph.built_in.middleware.base import get_base_middleware

class PrimaryAgent(BaseInternalAgent):
    SANITIZED_NAME = "supervisor"
    PROMPT_NAME = "primary_agent_v1"
    
    def get_toolset(self, model: str, custom_handoff_tools: list = [], web_search: bool = False) -> list:
        internal_tools = [
            zoan_internal_update_chat_title,
            zoan_internal_search_uploaded_documents,
        ]
        
        if web_search:
            if "openai" in model:
                internal_tools.append(ProviderBuiltInTool.OPENAI[BuiltinToolName.WEB_SEARCH])
            elif "anthropic" in model:
                internal_tools.append(ProviderBuiltInTool.ANTHROPIC[BuiltinToolName.WEB_SEARCH])
            
        return internal_tools + custom_handoff_tools
    
    def get_middleware(self) -> list:
        base_middleware = get_base_middleware()
        return base_middleware
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        llm = self._construct_llm_model(agent_config)
        toolset = self.get_toolset(
            agent_config.model,
            custom_handoff_tools=kwargs.get("custom_handoff_tools", []),
            web_search=kwargs.get("web_search", False)
        )
        
        system_prompt = self.get_prompt(current_avail_agents=kwargs.get("current_avail_agents", ""))
        
        middleware = self.get_middleware()

        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )
        
primary_agent = PrimaryAgent()