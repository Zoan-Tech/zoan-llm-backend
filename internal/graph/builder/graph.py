import copy
import threading
from typing import Any, Annotated, Dict, Sequence
from typing_extensions import TypedDict

from langchain_core.caches import InMemoryCache
from langgraph.cache.memory import InMemoryCache as GraphInMemoryCache
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
from internal.cache import GraphCache, graph_cache
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
from internal.graph.chat_model import ChatModel
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
    game_generator_v1.SANITIZED_NAME: game_generator_v1,
}

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    def __init__(
        self,
        graph_cache: GraphCache = graph_cache,
        prompt_manager: BasePromptManager = langfuse_prompt_manager,
        memory: Memory = memory,
        module_client: ModuleClient = module_client,
    ):
        self.graph_cache = graph_cache
        self.prompt_manager = prompt_manager
        self.memory = memory
        self.chat_model = ChatModel()
        self.tool_builder = ToolBuilder(module_client)
        # Initialize AgentBuilder
        self.agent_builder = AgentBuilder(self.chat_model, self.tool_builder, self.prompt_manager)
        # Thread lock for preventing race conditions during graph compilation
        self._compilation_lock = threading.RLock()
        # Lock for agent prompt loading to prevent concurrent modifications
        self._prompt_loading_lock = threading.RLock()

    def _get_available_agents(self, agent_configs: list[AgentConfig]) -> str:
        """Get a mapping of currently available agents by name with input sanitization."""
        try:
            available_agents = ""
            
            for agent_config in agent_configs:
                if not agent_config.is_primary:
                    available_agents += f"- {agent_config.name}:\n\t - Description: {agent_config.description or 'No description provided'}\n\t - Status: Currently {'Enabled' if agent_config.is_enabled else 'Disabled'}\n"
                
            return available_agents.strip()
        except Exception as e:
            logger.error(f"[GraphBuilder] Failed to get current available agents: {e}")
            return {}, "No other agents available."
        
    def build_subgraph(self, agent_configs: list[AgentConfig]) -> list[Any]:
        """
        Build a state graph for the agents.
        """
        successfully_added = []
        
        for agent_config in agent_configs:
            provider = agent_config.model.split(":")[0]
            if not agent_config.is_enabled:
                logger.debug(f"[GraphBuilder] Skipping disabled agent '{agent_config.name}'")
                continue
            
            try:
                if _normalize_agent_name(agent_config.name) in INTERNAL_AGENT.keys():
                    logger.debug(f"[GraphBuilder] Adding internal agent '{agent_config.name}'")
                    
                    agent = INTERNAL_AGENT[_normalize_agent_name(agent_config.name)].get_agent(
                        llm=self.chat_model._construct_llm_model(agent_config),
                        system_prompt=agent_config.system_prompt,
                        provider=provider,
                    )
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
    ) -> Any:
        """
        Build the primary agent for the graph.
        """
        primary_llm = self.chat_model._construct_llm_model(primary_agent_config)
        custom_handoff_tools = [
            create_handoff_tool(agent_name=agent_name)
            for agent_name in agent_names
        ]
        
        primary_agent = built_in_primary_agent.get_agent(
            llm=primary_llm,
            system_prompt=primary_agent_config.system_prompt,
            custom_handoff_tools=custom_handoff_tools,
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
    def build_graph(self, agent_configs: list[AgentConfig]) -> CompiledStateGraph:
        """
        Build a state graph for the agents.
        """
        primary_agent_config = next((agent_config for agent_config in agent_configs if agent_config.is_primary), None)
        if not primary_agent_config:
            raise GraphBuilderError("One agent must be marked as primary")
        
        agent_configs = [agent_config for agent_config in agent_configs if not agent_config.is_primary]

        agents = self.build_subgraph(agent_configs)
        agent_names = [agent.name for agent in agents]
        primary_agent = self.build_primary_agent(primary_agent_config, agent_names)

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
            cache=GraphInMemoryCache()
        )
        
    def _load_agent_prompt(self, agent_configs: list[AgentConfig]) -> list[AgentConfig]:
        """
        Load prompts for all agents and return a modified copy.
        This method creates a deep copy to avoid race conditions with concurrent access.
        """
        with self._prompt_loading_lock:
            # Create a deep copy to avoid modifying the original agents list
            agent_configs_copy = copy.deepcopy(agent_configs)
            current_avail_agents = self._get_available_agents(agent_configs_copy)
            
            for agent in agent_configs_copy:
                if _normalize_agent_name(agent.name) in INTERNAL_AGENT.keys():
                    agent.system_prompt = INTERNAL_AGENT[_normalize_agent_name(agent.name)].get_prompt(current_avail_agents=current_avail_agents)
                else:
                    agent.system_prompt = self.agent_builder._get_agent_construction_prompt(agent)
            
            return agent_configs_copy
        
    def _get_or_create_graph_safely(self, agent_configs: list[AgentConfig]) -> CompiledStateGraph:
        """
        Thread-safe method to get or create compiled graph.
        """
        try:
            # Generate cache key for these agents
            cache_key = self.graph_cache._generate_agent_config_hash(agent_configs)
            
            # Check if graph already exists in cache
            existing_graph = self.graph_cache.get(cache_key)
            if existing_graph:
                logger.debug(f"[GraphBuilder] Retrieved cached graph for key: {cache_key}")
                return existing_graph
            
            # Create new graph if not in cache
            logger.debug(f"[GraphBuilder] Creating new graph for key: {cache_key}")
            new_graph = self.build_graph(agent_configs)
            
            # Store in cache
            self.graph_cache.put(cache_key, new_graph)
            
            return new_graph
            
        except Exception as e:
            logger.error(f"[GraphBuilder] Error in graph compilation: {e}")
            # Fallback: create graph without caching
            return self.build_graph(agent_configs)

    def get_compiled_graph(
        self,
        agent_configs: list[AgentConfig]
    ) -> CompiledStateGraph:
        """
        Get a compiled state graph, using cache if available.
        Thread-safe implementation that prevents race conditions.
        """
        with self._compilation_lock:
            # Load prompts for all agents first, getting a safe copy
            agents_with_prompts = self._load_agent_prompt(agent_configs)
            
            # Use the thread-safe cache method
            return self._get_or_create_graph_safely(agents_with_prompts)