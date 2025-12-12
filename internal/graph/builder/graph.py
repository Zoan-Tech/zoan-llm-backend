import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Annotated, Dict, Sequence
from typing_extensions import TypedDict

from langchain_core.caches import InMemoryCache
from langgraph.cache.memory import InMemoryCache as LanggraphInMemoryCache
from langchain_core.globals import set_llm_cache
from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.pregel import Pregel
from langgraph._internal._runnable import RunnableCallable, RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, CachePolicy

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
    
logger = get_logger()

INTERNAL_AGENT: Dict[str, BaseInternalAgent] = {
    'primary_agent': built_in_primary_agent,
    game_generator_v1.SANITIZED_NAME: game_generator_v1,
}

# Default cache configuration
DEFAULT_MAX_CACHE_SIZE = 100  # Maximum number of compiled graphs to cache

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    
    Implements LRU (Least Recently Used) caching for compiled graphs to prevent memory issues.
    """
    def __init__(
        self,
        prompt_manager: BasePromptManager = langfuse_prompt_manager,
        memory: Memory = memory,
        module_client: ModuleClient = module_client,
        max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
    ):
        self.prompt_manager = prompt_manager
        self.memory = memory
        self.tool_builder = ToolBuilder(module_client)
        # Initialize AgentBuilder
        self.agent_builder = AgentBuilder(self.tool_builder, self.prompt_manager)
        # Thread lock for preventing race conditions during graph compilation
        self._compilation_lock = threading.RLock()
        # LRU cache for compiled graphs using OrderedDict
        self._graph_cache: OrderedDict[str, CompiledStateGraph] = OrderedDict()
        self._max_cache_size = max_cache_size
        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0
    
    def _generate_cache_key(self, agent_configs: list[AgentConfig], web_search: bool = False) -> str:
        """
        Generate a unique cache key based on agent configurations and web_search parameter.
        """
        # Create a serializable representation of the agent configs
        config_data = {
            'agent_configs': [config.model_dump() for config in agent_configs],
            'web_search': web_search,
        }
        # Convert to JSON string with sorted keys for consistent hashing
        config_json = json.dumps(config_data, sort_keys=True)
        # Generate hash
        return hashlib.sha256(config_json.encode()).hexdigest()
    
    def clear_cache(self) -> None:
        """
        Clear the graph cache and reset statistics.
        """
        with self._compilation_lock:
            cache_size = len(self._graph_cache)
            self._graph_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._cache_evictions = 0
            logger.info(f"[GraphBuilder] Graph cache cleared ({cache_size} entries removed)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache hits, misses, evictions, size, and hit rate
        """
        with self._compilation_lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0.0
            
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "evictions": self._cache_evictions,
                "current_size": len(self._graph_cache),
                "max_size": self._max_cache_size,
                "hit_rate_percent": round(hit_rate, 2),
            }
    
    def _evict_lru_entry(self) -> None:
        """
        Evict the least recently used entry from the cache.
        Called internally when cache is full.
        """
        if self._graph_cache:
            # Remove the first (oldest) item from OrderedDict
            evicted_key, _ = self._graph_cache.popitem(last=False)
            self._cache_evictions += 1
            logger.debug(f"[GraphBuilder] Evicted LRU cache entry: {evicted_key[:16]}...")

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
                raise GraphBuilderError(f"{agent_config.name} is broken. Please check the agent configuration and try again.") from e

        return successfully_added
    
    def build_primary_agent(
        self,
        primary_agent_config: AgentConfig,
        agent_names: list[Any],
        web_search: bool = False,
        current_avail_agents: str = "",
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
            current_avail_agents=current_avail_agents,
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
        agent_status = "\n".join([f"- {agent.name}: {agent.description}. Availability: {agent.is_enabled}" for agent in agent_configs])

        agents = self.build_subgraph(agent_configs)
        agent_names = [agent.name for agent in agents]
        primary_agent = self.build_primary_agent(primary_agent_config, agent_names, web_search=web_search, current_avail_agents=agent_status)

        builder = StateGraph(state_schema=_OuterState)
        builder.add_node(
            primary_agent,
            destinations=tuple(agent_names) + (END, ),
            retry_policy=RetryPolicy(),
            cache_policy=CachePolicy(ttl=900),
        )
        for agent in agents:
            builder.add_node(
                agent.name,
                self._make_call_agent(agent), 
                retry_policy=RetryPolicy(),
                cache_policy=CachePolicy(ttl=900),
            )
            builder.add_edge(agent.name, primary_agent.name)
            
        builder.add_edge(START, primary_agent.name)
        
        return builder.compile(
            cache=LanggraphInMemoryCache(),
            checkpointer=self.memory.saver,
            store=self.memory.store,
        )

    def get_compiled_graph(
        self,
        agent_configs: list[AgentConfig],
        web_search: bool = False,
    ) -> CompiledStateGraph:
        """
        Get a compiled state graph with thread-safe compilation and LRU caching.
        
        The cache uses LRU eviction when max_cache_size is reached.
        """
        # Generate cache key
        cache_key = self._generate_cache_key(agent_configs, web_search)
        
        # Check if graph is already cached
        if cache_key in self._graph_cache:
            with self._compilation_lock:
                # Move to end (mark as recently used)
                self._graph_cache.move_to_end(cache_key)
                self._cache_hits += 1
            
            stats = self.get_cache_stats()
            logger.debug(
                f"[GraphBuilder] Cache hit for key: {cache_key[:16]}... "
                f"(hits: {stats['hits']}, misses: {stats['misses']}, "
                f"hit rate: {stats['hit_rate_percent']}%)"
            )
            return self._graph_cache[cache_key]
        
        # Build and cache the graph
        with self._compilation_lock:
            # Double-check after acquiring lock
            if cache_key in self._graph_cache:
                self._graph_cache.move_to_end(cache_key)
                self._cache_hits += 1
                return self._graph_cache[cache_key]
            
            # Cache miss - need to build
            self._cache_misses += 1
            
            # Evict LRU entry if cache is full
            if len(self._graph_cache) >= self._max_cache_size:
                self._evict_lru_entry()
            
            logger.debug(f"[GraphBuilder] Building new graph for key: {cache_key[:16]}...")
            compiled_graph = self.build_graph(agent_configs, web_search=web_search)
            self._graph_cache[cache_key] = compiled_graph
            
            stats = self.get_cache_stats()
            logger.info(
                f"[GraphBuilder] Graph cached ({stats['current_size']}/{stats['max_size']}). "
                f"Stats - hits: {stats['hits']}, misses: {stats['misses']}, "
                f"evictions: {stats['evictions']}, hit rate: {stats['hit_rate_percent']}%"
            )
            
            return compiled_graph