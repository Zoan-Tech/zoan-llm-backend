import threading
import copy
from typing import Dict
from langfuse import observe

from langgraph.graph.state import CompiledStateGraph

from model import (
    AgentConfig,
)

from graph.chat_model import ChatModel
from graph.builder.tool import ToolBuilder
from graph.builder.agent import AgentBuilder
from cache import GraphCache, graph_cache
from prompt import BasePromptManager, langfuse_prompt_manager
from graph.memory import Memory, memory
from graph.internal.base import BaseInternalAgent
from graph.internal.game_generator import game_generator
from graph.internal.primary_agent import primary_agent

from module.client import ModuleClient, module_client

from utils.exception_handler import (
    GraphBuilderError,
    graph_builder_exception_handler,
)
from utils.helper import _sanitize_name
from utils.enums import *

from config.logging import get_logger


logger = get_logger()

INTERNAL_AGENT: Dict[str, BaseInternalAgent] = {
    primary_agent.SANITIZED_NAME: primary_agent,
    game_generator.SANITIZED_NAME: game_generator,
}

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    PROMPT_AGENT_CONSTRUCTION = "Agent Construction"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "Primary Agent Construction"

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

    def _get_available_agents(self, agents: list[AgentConfig]) -> str:
        """Get a mapping of currently available agents by name with input sanitization."""
        try:
            available_agents = ""
            
            for agent in agents:
                if not agent.is_primary:
                    available_agents += f"- {agent.name}:\n\t - Description: {agent.description or 'No description provided'}\n\t - Status: {'Enabled' if agent.is_enabled else 'Disabled'}\n"
                
            return available_agents.strip()
        except Exception as e:
            logger.error(f"[GraphBuilder] Failed to get current available agents: {e}")
            return {}, "No other agents available."
        
    def build_subgraph(self, agents: list[AgentConfig]) -> list:
        """
        Build a state graph for the agents.
        """
        successfully_added = []
        
        for agent_config in agents:
            if not agent_config.is_enabled:
                logger.debug(f"[GraphBuilder] Skipping disabled agent '{agent_config.name}'")
                continue
            try:
                if _sanitize_name(agent_config.name.lower()) in INTERNAL_AGENT.keys():
                    logger.debug(f"[GraphBuilder] Adding internal agent '{agent_config.name}'")
                    
                    agent = INTERNAL_AGENT[_sanitize_name(agent_config.name.lower())].get_agent(
                        llm=self.chat_model._construct_llm_model(agent_config),
                        system_prompt=agent_config.system_prompt
                    )
                    successfully_added.append(agent)
                else:
                    agent = self.agent_builder.build_agent(agent_config)
                    successfully_added.append(agent)
                    
            except Exception as e:
                logger.error(f"[GraphBuilder] Failed to build agent '{agent_config.name}': {e}")
                # Continue with other agents rather than failing completely
                continue

        return successfully_added

    @observe(name="build_graph")
    @graph_builder_exception_handler("Failed to build state graph")
    def build_graph(self, agents: list[AgentConfig]) -> CompiledStateGraph:
        """
        Build a state graph for the agents.
        """
        if not agents:
            raise GraphBuilderError("At least one agent configuration is required")

        primary_agent_config = next((agent for agent in agents if agent.is_primary), None)
        if not primary_agent_config:
            raise GraphBuilderError("One agent must be marked as primary")
        
        agents = [agent for agent in agents if not agent.is_primary]

        subgraph = self.build_subgraph(agents)

        primary_llm = self.chat_model._construct_llm_model(primary_agent_config)
        supervisor = primary_agent.get_agent(
            llm=primary_llm,
            system_prompt=primary_agent_config.system_prompt,
            agents=subgraph,
        )

        return supervisor.compile(
            checkpointer=self.memory.saver,
            store=self.memory.store,
        )
        
    def _load_agent_prompt(self, agents: list[AgentConfig]) -> list[AgentConfig]:
        """
        Load prompts for all agents and return a modified copy.
        This method creates a deep copy to avoid race conditions with concurrent access.
        """
        with self._prompt_loading_lock:
            # Create a deep copy to avoid modifying the original agents list
            agents_copy = copy.deepcopy(agents)
            current_avail_agents = self._get_available_agents(agents_copy)
            
            for agent in agents_copy:
                if _sanitize_name(agent.name.lower()) in INTERNAL_AGENT.keys():
                    agent.system_prompt = INTERNAL_AGENT[_sanitize_name(agent.name.lower())].get_prompt(current_avail_agents=current_avail_agents)
                else:
                    agent.system_prompt = self.agent_builder._get_agent_construction_prompt(agent)
            
            return agents_copy
        
    def _get_or_create_graph_safely(self, agents: list[AgentConfig]) -> CompiledStateGraph:
        """
        Thread-safe method to get or create compiled graph.
        """
        try:
            # Generate cache key for these agents
            cache_key = self.graph_cache._generate_agent_config_hash(agents)
            
            # Check if graph already exists in cache
            existing_graph = self.graph_cache.get(cache_key)
            if existing_graph:
                logger.debug(f"[GraphBuilder] Retrieved cached graph for key: {cache_key}")
                return existing_graph
            
            # Create new graph if not in cache
            logger.debug(f"[GraphBuilder] Creating new graph for key: {cache_key}")
            new_graph = self.build_graph(agents)
            
            # Store in cache
            self.graph_cache.put(cache_key, new_graph)
            
            return new_graph
            
        except Exception as e:
            logger.error(f"[GraphBuilder] Error in graph compilation: {e}")
            # Fallback: create graph without caching
            return self.build_graph(agents)

    def get_compiled_graph(
        self,
        agents: list[AgentConfig]
    ) -> CompiledStateGraph:
        """
        Get a compiled state graph, using cache if available.
        Thread-safe implementation that prevents race conditions.
        """
        with self._compilation_lock:
            # Load prompts for all agents first, getting a safe copy
            agents_with_prompts = self._load_agent_prompt(agents)
            
            # Use the thread-safe cache method
            return self._get_or_create_graph_safely(agents_with_prompts)
