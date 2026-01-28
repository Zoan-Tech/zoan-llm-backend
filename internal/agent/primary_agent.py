from langchain.agents import create_agent

from internal.agent.base import BaseInternalAgent
from internal.agent.tools.base import (
    ProviderBuiltInTool,
    BuiltinToolName,
    search_knowledge_base,
)
from internal.agent.tools.primary_agent import (
    zoan_internal_update_chat_title,
)
from model.completion import AgentConfig
from internal.agent.middleware.base import get_base_middleware

class PrimaryAgent(BaseInternalAgent):
    SANITIZED_NAME = "supervisor"
    PROMPT_NAME = "primary_agent_v1"
    
    def get_toolset(self, model: str, web_search: bool = False) -> list:
        internal_tools = [
            zoan_internal_update_chat_title,
            search_knowledge_base,
        ]
        
        if web_search:
            if "openai" in model:
                internal_tools.append(ProviderBuiltInTool.OPENAI[BuiltinToolName.WEB_SEARCH])
            elif "anthropic" in model:
                internal_tools.append(ProviderBuiltInTool.ANTHROPIC[BuiltinToolName.WEB_SEARCH])
            
        return internal_tools + self.handoff_tools
    
    def get_middleware(self) -> list:
        base_middleware = get_base_middleware()
        return base_middleware
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        self._prepare_handoff_tools(handoff_instructions=kwargs.get("handoff_instructions", {}))
        
        llm = self._construct_llm_model(agent_config)
        toolset = self.get_toolset(
            agent_config.model,
            web_search=kwargs.get("web_search", False)
        )
            
        system_prompt = self.get_prompt(current_avail_agents=kwargs.get("current_avail_agents", ""))
        
        middleware = ()

        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
        )
        
primary_agent = PrimaryAgent()