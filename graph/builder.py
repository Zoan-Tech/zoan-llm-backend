import os
import threading
import copy
from typing import Any, Dict, Optional, Tuple
from langfuse import observe

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import StructuredTool

from model import (
    AgentConfig,
    StepModule,
    AgentWorkflow,
)

from graph.chat_model import ChatModel
from graph.tool import ToolBuilder
from cache import GraphCache, graph_cache
from prompt import BasePromptManager, langfuse_prompt_manager
from graph.memory import Memory, memory
from graph.internal.base import BaseInternalAgent
from graph.internal.game_generator import game_generator
from graph.internal.primary_agent import primary_agent

from module.client import ModuleClient, module_client

from utils.exception_handler import (
    GraphBuilderError,
    PromptNotFoundError,
    AgentConfigurationError,
    graph_builder_exception_handler,
    safe_operation,
    validation_handler,
)
from utils.helper import _sanitize_name
from utils.enums import *

from config import Config
from config.logging import get_logger
import html
import re

logger = get_logger()

INTERNAL_AGENT: Dict[str, BaseInternalAgent] = {
    primary_agent.SANITIZED_NAME: primary_agent,
    game_generator.SANITIZED_NAME: game_generator,
}

class AgentBuilder:
    # Resource limits to prevent exhaustion attacks
    MAX_WORKFLOWS_PER_AGENT = 50
    MAX_STEPS_PER_WORKFLOW = 100
    MAX_TOOLS_TOTAL = 200
    
    def __init__(self, chat_model: ChatModel, tool_builder: ToolBuilder, prompt_manager: BasePromptManager):
        self.chat_model = chat_model
        self.tool_builder = tool_builder
        self.prompt_manager = prompt_manager
        self.PROMPT_AGENT_CONSTRUCTION = "Agent Construction"
        self.PROMPT_PRIMARY_AGENT_CONSTRUCTION = "Primary Agent Construction"
    
    @safe_operation(default_return={})
    def _apply_response_mapping(self, raw: Dict[str, Any], mapping: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Apply response mapping with error handling."""
        if not mapping:
            return raw
        out: Dict[str, Any] = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw:
                out[dst_key] = raw[src_key]
        return out

    @observe(name="construct_agent_toolset")
    @safe_operation(default_return=[])
    def _construct_agent_toolset(self, workflows: list[AgentWorkflow]) -> list[StructuredTool]:
        """
        Constructs a list of tools from the agent workflows with resource limits.
        """
        # Validate resource limits to prevent DoS attacks
        if len(workflows) > self.MAX_WORKFLOWS_PER_AGENT:
            logger.warning(f"[GraphBuilder] Workflow count ({len(workflows)}) exceeds maximum ({self.MAX_WORKFLOWS_PER_AGENT}). Truncating.")
            workflows = workflows[:self.MAX_WORKFLOWS_PER_AGENT]
        
        tools = []
        total_steps = 0
        
        for workflow in workflows:
            # Validate workflow steps limit
            if len(workflow.steps) > self.MAX_STEPS_PER_WORKFLOW:
                logger.warning(f"[GraphBuilder] Workflow '{workflow.name}' has {len(workflow.steps)} steps, exceeding maximum ({self.MAX_STEPS_PER_WORKFLOW}). Truncating.")
                workflow.steps = workflow.steps[:self.MAX_STEPS_PER_WORKFLOW]
            
            for step in workflow.steps:
                total_steps += 1
                
                # Global tool limit check
                if len(tools) >= self.MAX_TOOLS_TOTAL:
                    logger.warning(f"[GraphBuilder] Tool limit ({self.MAX_TOOLS_TOTAL}) reached. Stopping tool construction.")
                    return tools
                
                try:
                    tool = self.tool_builder._construct_tool(workflow.name, step)
                    if tool:
                        tools.append(tool)
                except Exception as e:
                    logger.error(f"[GraphBuilder] Failed to construct tool for step '{step.name}' in workflow '{workflow.name}': {e}")
                    # Continue with other tools rather than failing completely
                    continue
    
        logger.debug(f"[GraphBuilder] Created {len(tools)} tools from {len(workflows)} workflows with {total_steps} total steps")
        return tools
    
    def _sanitize_prompt_input(self, text: str) -> str:
        """
        Sanitize user input to prevent prompt injection attacks.
        """
        if not text or not isinstance(text, str):
            return "No information provided"
        
        # Remove potential prompt injection patterns
        sanitized = text.strip()
        
        # Remove markdown that could break prompt structure
        sanitized = re.sub(r'#{1,6}\s', '', sanitized)  # Remove markdown headers
        sanitized = re.sub(r'```[\s\S]*?```', '', sanitized)  # Remove code blocks
        sanitized = re.sub(r'`[^`]*?`', '', sanitized)  # Remove inline code
        
        # HTML escape to prevent XSS-style attacks
        sanitized = html.escape(sanitized)
        
        # Limit length to prevent massive prompts
        if len(sanitized) > 1000:
            sanitized = sanitized[:997] + "..."
            logger.warning("[GraphBuilder] Truncated excessively long input text")
        
        return sanitized

    @safe_operation(default_return="No workflows defined.")
    def _construct_agent_workflow_prompt(self, workflows: list[AgentWorkflow], is_primary: bool = False) -> str:
        """
        Mapping agent workflows into an instruction prompt with input sanitization.
        """
        if not workflows:
            if not is_primary:
                return "No workflows defined."
            else:
                return "Primary agent has no workflows defined."
            
        def format_step(steps: list[StepModule]) -> str:
            if not steps:
                return "No steps defined"
            return "\n".join(
                f"- {self._sanitize_prompt_input(step.name)}: {self._sanitize_prompt_input(step.description or step.name)}"
                for step in steps
            )
        
        template = """
## Workflow: {name}

### Description:
{description}

### Steps:
{steps}
"""

        return "\n".join(
            template.format(
                name=self._sanitize_prompt_input(workflow.name),
                description=self._sanitize_prompt_input(workflow.description or "No description provided"),
                steps=format_step(workflow.steps)
            )
            for workflow in workflows
        )
    
    @observe(name="get_agent_construction_prompt")
    @graph_builder_exception_handler("Failed to get agent construction prompt")
    def _get_agent_construction_prompt(self, agent_config: AgentConfig) -> str:
        """
        Get the prompt for constructing the agent.
        """
        prompt = self.prompt_manager.get_prompt(
            self.PROMPT_AGENT_CONSTRUCTION,
            label=Config.LANGFUSE_PROMPT_LABEL,
            version=Config.LANGFUSE_VERSION_ID,
        )
        if not prompt:
            raise PromptNotFoundError(f"Prompt '{self.PROMPT_AGENT_CONSTRUCTION}' not found in Langfuse.")
        
        compiled_prompt = prompt.compile(
            description=agent_config.description or "No description provided",
            instruction=agent_config.instruction or "No instruction provided",
            workflows=self._construct_agent_workflow_prompt(agent_config.workflows)
        )
        
        return compiled_prompt

    @validation_handler("Agent configuration validation failed")
    def _validate_agent_config(self, agent_config: AgentConfig) -> None:
        """Validate agent configuration before building."""
        if not agent_config.model:
            raise AgentConfigurationError("Model name is required")

        # Validate workflows have steps
        for workflow in agent_config.workflows:
            if not workflow.steps:
                logger.warning(f"[GraphBuilder] Workflow '{workflow.name}' has no steps")

    @observe(name="build_agent")
    @graph_builder_exception_handler("Failed to build agent")
    def build_agent(self, agent_config: AgentConfig):
        """
        Build a react agent using the provided agent configuration.
        """
        # Validate configuration first
        self._validate_agent_config(agent_config)
        
        # Initialize the chat model
        llm = self.chat_model._construct_llm_model(agent_config)

        # Construct tools
        toolset = self._construct_agent_toolset(agent_config.workflows)
        
        # Create the react agent
        return create_react_agent(llm, tools=toolset, prompt=agent_config.system_prompt, name=_sanitize_name(agent_config.name.lower()))

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
        