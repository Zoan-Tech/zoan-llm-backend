from typing import Any, Dict, Optional
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

logger = get_logger()

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    PROMPT_AGENT_CONSTRUCTION = "Agent Construction"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "Primary Agent Construction"
    PROMPT_GAME_GENERATOR_CONSTRUCTION = "Game Generator"
    GAME_GENERATOR = "Game Generator"

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
        Constructs a list of tools from the agent workflows.
        """
        tools = []
        
        for workflow in workflows: 
            for step in workflow.steps:
                try:
                    tool = self.tool_builder._construct_tool(workflow.name, step)
                    if tool:
                        tools.append(tool)
                except Exception as e:
                    logger.error(f"[GraphBuilder] Failed to construct tool for step '{step.name}' in workflow '{workflow.name}': {e}")
                    # Continue with other tools rather than failing completely
                    continue
    
        return tools
    
    @safe_operation(default_return="No workflows defined.")
    def _construct_agent_workflow_prompt(self, workflows: list[AgentWorkflow], is_primary: bool = False) -> str:
        """
        Mapping agent workflows into an instruction prompt.
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
                f"- {step.name}: {step.description or step.name}"
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
                name=workflow.name,
                description=workflow.description or "No description provided",
                steps=format_step(workflow.steps)
            )
            for workflow in workflows
        )
    
    @observe(name="get_agent_construction_prompt")
    @graph_builder_exception_handler("Failed to get agent construction prompt")
    def _get_agent_construction_prompt(self, agent_config: AgentConfig, is_primary: bool = False) -> str:
        """
        Get the prompt for constructing the agent.
        """
        if is_primary:
            prompt = self.prompt_manager.get_prompt(self.PROMPT_PRIMARY_AGENT_CONSTRUCTION)
            if not prompt:
                raise PromptNotFoundError(f"Prompt '{self.PROMPT_AGENT_CONSTRUCTION}' not found in Langfuse.")
            compiled_prompt = prompt.compile()
            return compiled_prompt
        elif agent_config.name == self.GAME_GENERATOR:
            prompt = self.prompt_manager.get_prompt(self.PROMPT_GAME_GENERATOR_CONSTRUCTION)
            if not prompt:
                raise PromptNotFoundError(f"Prompt '{self.PROMPT_GAME_GENERATOR_CONSTRUCTION}' not found in Langfuse.")
            
            compiled_prompt = prompt.compile()
            return compiled_prompt
        else:
            prompt = self.prompt_manager.get_prompt(self.PROMPT_AGENT_CONSTRUCTION)
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
        
        # Validate that we can get the API key
        decrypted_key = agent_config.get_decrypted_api_key()
        if not decrypted_key:
            raise AgentConfigurationError("Failed to decrypt API key or key is empty")
            
        # Validate workflows have steps
        for workflow in agent_config.workflows:
            if not workflow.steps:
                logger.warning(f"[GraphBuilder] Workflow '{workflow.name}' has no steps")

    def _construct_llm(self, agent_config: AgentConfig) -> Any:
        """
        Initialize the chat model based on the agent configuration.
        """
        model = "gpt-4.1" if agent_config.name == self.GAME_GENERATOR else agent_config.model
        return init_chat_model(
            model=model,
            use_responses_api=True,
            stream_usage=agent_config.stream_usage,
            api_key=agent_config.get_decrypted_api_key(),
            timeout=120,
            **agent_config.model_kwargs.model_dump(exclude_none=True)
        )

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
        tools = self._construct_agent_toolset(agent_config.workflows) if agent_config.name != self.GAME_GENERATOR else [
            {
                "type": "code_interpreter",
                "container": {"type": "auto"},
            }
        ]

        # Get prompt
        prompt = self._get_agent_construction_prompt(agent_config)

        # Create the react agent
        return create_react_agent(llm, tools=tools, prompt=prompt, name=_sanitize_name(agent_config.name.lower()))

    @observe(name="build_graph")
    @graph_builder_exception_handler("Failed to build state graph")
    def build_graph(self, agents: list[AgentConfig]) -> CompiledStateGraph:
        """
        Build a state graph for the agents.
        """
        if not agents:
            raise GraphBuilderError("At least one agent configuration is required")

        primary_agent_config = agents.pop(0)
        primary_llm = self._construct_llm(primary_agent_config)
        primary_prompt = self._get_agent_construction_prompt(primary_agent_config, is_primary=True)
        primary_tools = None

        successfully_added = []
        
        for agent_config in agents:
            try:
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
            output_mode="full_history",
            tools=primary_tools,
            model=primary_llm,
            prompt=primary_prompt,
        )

        return primary_agent.compile(
            checkpointer=self.memory.saver,
            store=self.memory.store,
        )

    def get_compiled_graph(
        self,
        agents: list[AgentConfig]
    ) -> CompiledStateGraph:
        """
        Get a compiled state graph, using cache if available.
        """
        return self.graph_cache.get_or_store_compiled_graph(
            agents,
            lambda agents: self.build_graph(agents)
        )
        