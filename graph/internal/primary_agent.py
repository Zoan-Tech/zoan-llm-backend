from langgraph_supervisor import create_supervisor
from config import Config
from graph.internal.base import BaseInternalAgent
from graph.internal.tools.primary_agent import update_chat_title

class PrimaryAgent(BaseInternalAgent):
    SANITIZED_NAME = "primary_agent"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "primary_agent_v1"
    
    def get_prompt(self, **kwargs) -> str:
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_PRIMARY_AGENT_CONSTRUCTION,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        compiled_prompt = prompt.compile(**kwargs)
        return compiled_prompt
    
    def get_toolset(self):
        return [update_chat_title]
    
    def get_agent(self, llm, system_prompt: str, **kwargs):
        toolset = self.get_toolset()
        return create_supervisor(
            agents=kwargs.get("agents", []),
            output_mode="last_message",
            tools=toolset,
            model=llm,
            prompt=system_prompt,
            add_handoff_messages=False,
        )
        
primary_agent = PrimaryAgent()