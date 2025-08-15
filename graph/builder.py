from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, create_model
from langfuse import Langfuse
import logging

from langgraph.graph import END, START
from langgraph.graph.state import StateGraph, CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model
from module.client import ModuleClient
from langchain_core.tools import StructuredTool

from model import (
    AgentConfig,
    StepModule,
    AgentWorkflow,
)

from utils.helper import to_py_type
from utils.exception_handler import (
    GraphBuilderError,
    PromptNotFoundError,
    AgentConfigurationError,
    graph_builder_exception_handler,
    safe_operation,
    validation_handler,
    api_operation_handler
)

logger = logging.getLogger(__name__)

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    PROMPT_AGENT_CONSTRUCTION = "Agent Construction"

    def __init__(
        self,
        module_client: ModuleClient,
        langfuse_client: Langfuse,
        checkpointer: Optional[Any] = None,
        store: Optional[Any] = None
    ):
        self.module_client = module_client
        self.langfuse_client = langfuse_client
        self.checkpointer = checkpointer
        self.store = store

    @graph_builder_exception_handler("Failed to build args schema")
    def _build_args_schema_from_step(self, step_module: StepModule) -> type[BaseModel]:
        """
        Build a Pydantic model for the arguments of a step module.
        """
        args_spec = step_module.args or {}
        if not args_spec:
            return create_model(f"{step_module.name}Args")  # no-arg tool

        fields = {}
        for arg_name, spec in args_spec.items():
            if not isinstance(spec, dict):
                logger.warning(f"Invalid spec for argument '{arg_name}' in step '{step_module.name}'. Expected dict, got {type(spec)}")
                continue
                
            arg_type = to_py_type(spec.get("type", "str"))
            is_required = spec.get("required", True)
            description = spec.get("description", "")
            
            fields[arg_name] = (
                arg_type,
                Field(... if is_required else None, description=description)
            )
        
        return create_model(f"{step_module.name}Args", **fields)
    
    @safe_operation(default_return={})
    def _apply_response_mapping(self, raw: Dict[str, Any], mapping: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Apply response mapping with error handling."""
        if not mapping:
            return raw
        
        mapped_response = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw:
                mapped_response[dst_key] = raw[src_key]
            else:
                logger.warning(f"Source key '{src_key}' not found in response")
        return mapped_response

    @graph_builder_exception_handler("Failed to construct module tool")
    def _construct_module_tool(self, workflow_name: str, step_module: StepModule) -> StructuredTool:
        """Construct a module tool with proper error handling."""
        try:
            ArgsSchema = self._build_args_schema_from_step(step_module)

            @api_operation_handler(f"Module execution failed for {step_module.name}")
            def _run(**kwargs):
                if step_module.name == "human_input":
                    return {
                        "message": "Ask for user's input about: {}".format(step_module.description)
                    }
                else:
                    payload = dict(kwargs)
                    result = self.module_client.execute_module(step_module.name, payload=payload)
                    return self._apply_response_mapping(result, step_module.response_mapping)


            decor_workflow_name = workflow_name.lower().split(" ").join("_"),
            return StructuredTool.from_function(
                name=f"{decor_workflow_name}-{step_module.name}",
                description=step_module.description or "No description provided",
                func=_run,
                args_schema=ArgsSchema,
                return_direct=False,
            )
        except Exception as e:
            logger.error(f"Error during tool construction for {step_module.name}: {e}")
            raise
    
    @safe_operation(default_return=[])
    def _construct_agent_toolset(self, workflows: list[AgentWorkflow]) -> list[StructuredTool]:
        """
        Constructs a list of tools from the agent workflows.
        """
        tools = []
        
        if not workflows:
            logger.warning("No workflows provided for agent toolset construction")
            return tools
            
        for workflow in workflows:
            if not workflow.steps:
                logger.warning(f"No steps found in workflow '{workflow.name}'")
                continue
                
            for step in workflow.steps:
                try:
                    tool = self._construct_module_tool(workflow.name, step)
                    tools.append(tool)
                except Exception as e:
                    logger.error(f"Failed to construct tool for step '{step.name}' in workflow '{workflow.name}': {e}")
                    # Continue with other tools rather than failing completely
                    continue
            
        return tools
    
    @safe_operation(default_return="No workflows defined.")
    def _construct_agent_workflow_prompt(self, workflows: list[AgentWorkflow]) -> str:
        """
        Mapping agent workflows into an instruction prompt.
        """
        if not workflows:
            return "No workflows defined."
            
        def format_step(steps: list[StepModule]) -> str:
            if not steps:
                return "No steps defined"
            return "\n".join(
                f"- {step.name}: {step.description or 'No description provided'}"
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
    
    @graph_builder_exception_handler("Failed to get agent construction prompt")
    def _get_agent_construction_prompt(self, agent_config: AgentConfig) -> str:
        """
        Get the prompt for constructing the agent.
        """
        prompt = self.langfuse_client.get_prompt(self.PROMPT_AGENT_CONSTRUCTION)
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
                logger.warning(f"Workflow '{workflow.name}' has no steps")

    @graph_builder_exception_handler("Failed to build agent")
    def build_agent(self, agent_config: AgentConfig):
        """
        Build a react agent using the provided agent configuration.
        """
        # Validate configuration first
        self._validate_agent_config(agent_config)
        
        # Initialize the chat model
        llm = init_chat_model(
            model=agent_config.model,
            stream_usage=agent_config.stream_usage,
            api_key=agent_config.get_decrypted_api_key(),
            **agent_config.model_kwargs.model_dump(exclude_none=True)
        )

        # Construct tools
        tools = self._construct_agent_toolset(agent_config.workflows) 
        if not tools:
            logger.warning("No tools were successfully constructed for the agent")

        # Get prompt
        prompt = self._get_agent_construction_prompt(agent_config)

        # Create the react agent
        return create_react_agent(llm, tools=tools, prompt=prompt)

    @graph_builder_exception_handler("Failed to build state graph")
    def build_graph(self, agents: list[AgentConfig]) -> CompiledStateGraph:
        """
        Build a state graph for the agents.
        """
        if not agents:
            raise GraphBuilderError("At least one agent configuration is required")
            
        # Create state graph - you might need to define a proper state schema
        graph = StateGraph(dict)

        primary_agent_config = agents.pop(0)
        primary_agent = self.build_agent(primary_agent_config)
        graph.add_node(primary_agent_config.name, primary_agent)
        graph.add_edge(START, primary_agent_config.name)
        graph.add_edge(primary_agent_config.name, END)
        
        successfully_added = []
        
        for agent_config in agents:
            try:
                agent = self.build_agent(agent_config)
                
                graph.add_node(agent_config.name, agent)
                
                successfully_added.append((agent_config.name, agent))
                logger.info(f"Successfully added agent '{agent_config.name}' to graph")
                
            except Exception as e:
                logger.error(f"Failed to build agent '{agent_config.name}': {e}")
                # Continue with other agents rather than failing completely
                continue
        
        # Add proper graph edges based on your workflow logic
        if len(successfully_added):
            # Add edges between consecutive agents (if that's your intended flow)
            for (agent_name, agent) in successfully_added:
                graph.add_edge(primary_agent_config.name, agent_name)
                graph.add_edge(agent_name, END)

        return graph.compile(
            checkpointer=self.checkpointer,
            store=self.store,
        )

