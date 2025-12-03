import threading
from typing import Any, Annotated, Dict, Sequence
from typing_extensions import TypedDict

from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache
from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.pregel import Pregel
from langgraph._internal._runnable import RunnableCallable, RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from langgraph_supervisor.handoff import _normalize_agent_name

from config.logging import get_logger
from internal.graph.built_in import (
    game_generator_v1,
    primary_agent as built_in_primary_agent,
)
from internal.graph.built_in.tools.primary_agent import create_handoff_tool
from internal.graph.built_in.base import BaseInternalAgent
from internal.graph.builder.agent import AgentBuilder
from internal.graph.builder.module.client import ModuleClient, module_client
from internal.graph.builder.prompt import BasePromptManager, langfuse_prompt_manager
from internal.graph.builder.tool import ToolBuilder
from internal.graph.memory import Memory, memory
from model import AgentConfig
from utils.enums import *
from utils.exception_handler import GraphBuilderError, graph_builder_exception_handler

set_llm_cache(InMemoryCache())

class _OuterState(TypedDict):
    """The state of the supervisor workflow."""
    messages: Annotated[Sequence[AnyMessage], add_messages]

class Context(TypedDict):
    image_urls: list[str]
    
logger = get_logger()

INTERNAL_AGENT: Dict[str, BaseInternalAgent] = {
    'primary_agent': built_in_primary_agent,
    game_generator_v1.SANITIZED_NAME: game_generator_v1,
}

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    def __init__(
        self,
        prompt_manager: BasePromptManager = langfuse_prompt_manager,
        memory: Memory = memory,
        module_client: ModuleClient = module_client,
    ):
        self.prompt_manager = prompt_manager
        self.memory = memory
        self.tool_builder = ToolBuilder(module_client)
        # Initialize AgentBuilder
        self.agent_builder = AgentBuilder(self.tool_builder, self.prompt_manager)
        # Thread lock for preventing race conditions during graph compilation
        self._compilation_lock = threading.RLock()

    def build_subgraph(self, agent_configs: list[AgentConfig]) -> list[Any]:
        """
        Build a state graph for the agents.
        """
        successfully_added = []
        
        for agent_config in agent_configs:
            if not agent_config.is_enabled:
                logger.debug(f"[GraphBuilder] Skipping disabled agent '{agent_config.name}'")
                continue
            
            try:
                if _normalize_agent_name(agent_config.name) in INTERNAL_AGENT.keys():
                    logger.debug(f"[GraphBuilder] Adding internal agent '{agent_config.name}'")
                    
                    agent = INTERNAL_AGENT[_normalize_agent_name(agent_config.name)].get_agent(agent_config)
                else:
                    agent = self.agent_builder.build_agent(agent_config)
                    
                successfully_added.append(agent)
                
            except Exception as e:
                logger.error(f"[GraphBuilder] Failed to build agent '{agent_config.name}': {e}")
                # Continue with other agents rather than failing completely
                continue

        return successfully_added
    
    def build_primary_agent(
        self,
        primary_agent_config: AgentConfig,
        agent_names: list[Any],
        web_search: bool = False,
    ) -> Any:
        """
        Build the primary agent for the graph.
        """
        custom_handoff_tools = [
            create_handoff_tool(agent_name=agent_name)
            for agent_name in agent_names
        ]
        
        primary_agent = built_in_primary_agent.get_agent(
            primary_agent_config,
            custom_handoff_tools=custom_handoff_tools,
            web_search=web_search,
        )
        return primary_agent
    
    def _make_call_agent(self, agent: Pregel[Any]) -> RunnableCallable:
        """Wrap agent to process its output correctly."""    
        def call_agent(state: dict, config: RunnableConfig) -> dict:
            output = agent.invoke(state, config)
            messages = output["messages"]
            if isinstance(messages[-1], ToolMessage):
                messages = messages[-2:]
            else:
                messages = messages[-1:]
                
            return {
                "messages": messages,
            }
        
        return RunnableCallable(call_agent)

    @graph_builder_exception_handler("Failed to build state graph")
    def build_graph(self, agent_configs: list[AgentConfig], web_search: bool = False) -> CompiledStateGraph:
        """
        Build a state graph for the agents.
        """
        primary_agent_config = next((agent_config for agent_config in agent_configs if agent_config.is_primary), None)
        if not primary_agent_config:
            raise GraphBuilderError("One agent must be marked as primary")
        
        agent_configs = [agent_config for agent_config in agent_configs if not agent_config.is_primary]

        agents = self.build_subgraph(agent_configs)
        agent_names = [agent.name for agent in agents]
        primary_agent = self.build_primary_agent(primary_agent_config, agent_names, web_search=web_search)

        builder = StateGraph(state_schema=_OuterState, context_schema=Context)
        builder.add_node(primary_agent, destinations=tuple(agent_names) + (END, ))
        for agent in agents:
            builder.add_node(
                agent.name,
                self._make_call_agent(agent), 
                retry_policy=RetryPolicy()
            )
            builder.add_edge(agent.name, primary_agent.name)
            
        builder.add_edge(START, primary_agent.name)
        
        return builder.compile(
            checkpointer=self.memory.saver,
            store=self.memory.store,
        )

    def get_compiled_graph(
        self,
        agent_configs: list[AgentConfig],
        web_search: bool = False,
    ) -> CompiledStateGraph:
        """
        Get a compiled state graph with thread-safe compilation.
        """
        with self._compilation_lock:
            return self.build_graph(agent_configs, web_search=web_search)