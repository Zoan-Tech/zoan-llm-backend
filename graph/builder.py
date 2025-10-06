import os
import threading
import copy
from typing import Any, Dict, Optional, Tuple
from langfuse import observe

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool

from model import (
    AgentConfig,
    StepModule,
    AgentWorkflow,
)

from graph.tool import ToolBuilder
from cache import GraphCache, DEFAULT_GRAPH_CACHE
from prompt import BasePromptManager, DEFAULT_PROMPT_MANAGER
from graph.memory import Memory, DEFAULT_MEMORY
from graph.game_generator import DEFAULT_GAME_GENERATOR
from langmem import create_manage_memory_tool, create_search_memory_tool

from module.client import ModuleClient, DEFAULT_MODULE_CLIENT

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

from config.logging import get_logger
import html
import re

logger = get_logger()

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    PROMPT_AGENT_CONSTRUCTION = "Agent Construction"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "Primary Agent Construction"

    def __init__(
        self,
        graph_cache: GraphCache = DEFAULT_GRAPH_CACHE,
        prompt_manager: BasePromptManager = DEFAULT_PROMPT_MANAGER,
        memory: Memory = DEFAULT_MEMORY,
        module_client: ModuleClient = DEFAULT_MODULE_CLIENT,
    ):
        self.graph_cache = graph_cache
        self.prompt_manager = prompt_manager
        self.memory = memory
        self.tool_builder = ToolBuilder(module_client)
        # Thread lock for preventing race conditions during graph compilation
        self._compilation_lock = threading.RLock()
        # Lock for agent prompt loading to prevent concurrent modifications
        self._prompt_loading_lock = threading.RLock()
    
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
    
    # Resource limits to prevent exhaustion attacks
    MAX_WORKFLOWS_PER_AGENT = 50
    MAX_STEPS_PER_WORKFLOW = 100
    MAX_TOOLS_TOTAL = 200

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
    def _get_agent_construction_prompt(self, agent_config: AgentConfig, is_primary: bool = False, **kwargs) -> str:
        """
        Get the prompt for constructing the agent.
        """
        if is_primary:
            current_avail_agents = kwargs.get("current_avail_agents", "No other agents available.")
            prompt = self.prompt_manager.get_prompt(
                self.PROMPT_PRIMARY_AGENT_CONSTRUCTION,
                label=os.getenv(SecretEnum.LANGFUSE_PROMPT_LABEL.value),
                version=os.getenv(SecretEnum.LANGFUSE_VERSION_ID.value),
            )
            if not prompt:
                raise PromptNotFoundError(f"Prompt '{self.PROMPT_AGENT_CONSTRUCTION}' not found in Langfuse.")
            logger.debug(f"Current available agents for primary: {current_avail_agents}")
            compiled_prompt = prompt.compile(
                current_avail_agents=current_avail_agents,
            )
            return compiled_prompt
        else:
            prompt = self.prompt_manager.get_prompt(
                self.PROMPT_AGENT_CONSTRUCTION,
                label=os.getenv(SecretEnum.LANGFUSE_PROMPT_LABEL.value),
                version=os.getenv(SecretEnum.LANGFUSE_VERSION_ID.value),
            )
            if not prompt:
                raise PromptNotFoundError(f"Prompt '{self.PROMPT_AGENT_CONSTRUCTION}' not found in Langfuse.")
            
            compiled_prompt = prompt.compile(
                description=self._sanitize_prompt_input(agent_config.description or "No description provided"),
                instruction=self._sanitize_prompt_input(agent_config.instruction or "No instruction provided"),
                workflows=self._construct_agent_workflow_prompt(agent_config.workflows)
            )
            
            return compiled_prompt

    @validation_handler("Agent configuration validation failed")
    def _validate_agent_config(self, agent_config: AgentConfig) -> None:
        """Validate agent configuration before building."""
        if not agent_config.model:
            raise AgentConfigurationError("Model name is required")
        
        # Ensure API key is set for the model provider
        self._ensure_provider_api_key(agent_config)
            
        # Validate workflows have steps
        for workflow in agent_config.workflows:
            if not workflow.steps:
                logger.warning(f"[GraphBuilder] Workflow '{workflow.name}' has no steps")

    def _construct_llm(self, agent_config: AgentConfig) -> Any:
        """
        Initialize the chat model based on the agent configuration.
        """ 
        return init_chat_model(
            model=agent_config.model,
            use_responses_api=True,
            stream_usage=agent_config.stream_usage,
            timeout=120,
            **agent_config.model_kwargs.model_dump(exclude_none=True)
        )
    
    def _ensure_provider_api_key(self, agent_config: AgentConfig) -> None:
        """Ensure the API key for the model provider is set in environment variables."""
        # Currently only OpenAI is supported
        if ( agent_config.model.startswith("openai:")
            or agent_config.model.startswith("gpt-")
            or agent_config.model.startswith("text-")
        ):
            if not os.getenv(SecretEnum.OPENAI_API_KEY.value):
                raise AgentConfigurationError("OPENAI_API_KEY environment variable is not set")
        elif ( agent_config.model.startswith("anthropic:")
            or agent_config.model.startswith("claude-")
        ):
            if not os.getenv(SecretEnum.ANTHROPIC_API_KEY.value):
                raise AgentConfigurationError("ANTHROPIC_API_KEY environment variable is not set")
        elif ( agent_config.model.startswith("deepseek:")
        ):
            if not os.getenv(SecretEnum.DEEPSEEK_API_KEY.value):
                raise AgentConfigurationError("DEEPSEEK_API_KEY environment variable is not set")
        elif ( agent_config.model.startswith("gemini:")
        ):
            if not os.getenv(SecretEnum.GEMINI_API_KEY.value):
                raise AgentConfigurationError("GEMINI_API_KEY environment variable is not set") 

    @observe(name="build_agent")
    @graph_builder_exception_handler("Failed to build agent")
    def build_agent(self, agent_config: AgentConfig):
        """
        Build a react agent using the provided agent configuration.
        """
        # Validate configuration first
        self._validate_agent_config(agent_config)
        
        # Initialize the chat model
        llm = self._construct_llm(agent_config)

        # Construct tools
        tools = self._construct_agent_toolset(agent_config.workflows)
        
        # Create the react agent
        return create_react_agent(llm, tools=tools, prompt=agent_config.system_prompt, name=_sanitize_name(agent_config.name.lower()))

    def _current_avail_agents(self, agents: list[AgentConfig]) -> Tuple[dict, str]:
        """Get a mapping of currently available agents by name with input sanitization."""
        try:
            agent_list = {}
            
            for agent in agents:
                if not agent.is_primary:
                    # Sanitize agent data to prevent prompt injection
                    sanitized_agent = {
                        "name": self._sanitize_prompt_input(agent.name),
                        "description": self._sanitize_prompt_input(agent.description or "No description provided"),
                        "is_enabled": agent.is_enabled
                    }
                    agent_list[sanitized_agent["name"]] = sanitized_agent
                
            agent_list_str = "\n".join(
                f"- {name}: {info.get('description', 'No description provided')} ({'Enabled' if info.get('is_enabled', True) else 'Disabled'})"
                for name, info in agent_list.items()
            ) if agent_list else "No other agents available."
            
            return agent_list, agent_list_str
        except Exception as e:
            logger.error(f"[GraphBuilder] Failed to get current available agents: {e}")
            return {}, "No other agents available."

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
        
        primary_llm = self._construct_llm(primary_agent_config)
        # Init primary tools with default memory tools
        # TODO: Re-enable memory tools when stable
        # primary_tools = [
        #     # Memory tools use LangGraph's BaseStore for persistence (4)
        #     create_manage_memory_tool(namespace=("memories",)),
        #     create_search_memory_tool(namespace=("memories",)),
        # ]
        primary_tools = None

        successfully_added = []
        
        for agent_config in agents:
            if not agent_config.is_enabled:
                logger.debug(f"[GraphBuilder] Skipping disabled agent '{agent_config.name}'")
                continue
            try:
                if _sanitize_name(agent_config.name.lower()) == DEFAULT_GAME_GENERATOR.SANITIZED_NAME:
                    logger.debug(f"[GraphBuilder] Adding Game Generator agent '{agent_config.name}'")
                    game_generator_agent = DEFAULT_GAME_GENERATOR.get_generator()
                    successfully_added.append(game_generator_agent)
                else:
                    agent = self.build_agent(agent_config)
                    successfully_added.append(agent)
                    
                # TODO: Re-enable handoff tools when stable
                # primary_tools.append(
                #     create_handoff_tool(
                #         agent_name=_sanitize_name(agent_config.name.lower()),
                #         name=f"handoff_to_{_sanitize_name(agent_config.name.lower())}",
                #         description=f"Hand off to agent {_sanitize_name(agent_config.name.lower())}",
                #     )
                # )
                
            except Exception as e:
                logger.error(f"[GraphBuilder] Failed to build agent '{agent_config.name}': {e}")
                # Continue with other agents rather than failing completely
                continue

        primary_agent = create_supervisor(
            agents=successfully_added,
            output_mode="last_message",
            tools=primary_tools,
            model=primary_llm,
            prompt=primary_agent_config.system_prompt,
            add_handoff_messages=False
        )

        return primary_agent.compile(
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
            
            for agent in agents_copy:
                if agent.is_primary:        
                    _, current_avail_agents = self._current_avail_agents(agents_copy)
                    agent.system_prompt = self._get_agent_construction_prompt(agent, is_primary=True, current_avail_agents=current_avail_agents)
                elif _sanitize_name(agent.name.lower()) == DEFAULT_GAME_GENERATOR.SANITIZED_NAME:
                    agent.system_prompt = DEFAULT_GAME_GENERATOR.get_game_generation_prompt()
                else:
                    agent.system_prompt = self._get_agent_construction_prompt(agent)
            
            return agents_copy

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
        