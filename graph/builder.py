from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, create_model
from langfuse import Langfuse, observe
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
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
)

logger = logging.getLogger(__name__)


def _spec_get(spec: Any, key: str, default: Any = None):
    # supports both dict-like and attr-like specs
    if isinstance(spec, dict):
        return spec.get(key, default)
    return getattr(spec, key, default)

class GraphBuilder:
    """
    Builds a graph for the agent workflow.
    Initializes the chat model and constructs tools based on the agent configuration.
    """
    PROMPT_AGENT_CONSTRUCTION = "Agent Construction"
    PROMPT_PRIMARY_AGENT_CONSTRUCTION = "Primary Agent Construction"

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
    def _build_args_schema_from_step(self, workflow_name: str, step_module: StepModule) -> type[BaseModel]:
        """
        Build a Pydantic model for the arguments of a step module.
        """
        args_spec = step_module.args or {}
        model_name = f"{workflow_name}_{step_module.name}_Args".replace(" ", "_")
        
        if not args_spec:
            return create_model(model_name)  # no-arg tool

        fields: Dict[str, tuple] = {}
        for arg_name, spec in args_spec.items():
            py_type = to_py_type(_spec_get(spec, "type", "str"))
            required = bool(_spec_get(spec, "required", False))
            desc = _spec_get(spec, "description", None)
            default_val = _spec_get(spec, "value", None)
            
            default = ... if required else default_val

            fields[arg_name] = (py_type, Field(default=default, description=desc))
        
        return create_model(model_name, **fields)
    
    @safe_operation(default_return={})
    def _apply_response_mapping(self, raw: Dict[str, Any], mapping: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Apply response mapping with error handling."""
        if not mapping:
            return raw
        out: Dict[str, Any] = {}
        for src_key, dst_key in mapping.items():
            if src_key in raw:
                out[dst_key] = raw[src_key]
            else:
                logger.warning(f"Source key '{src_key}' not found in response")
        return out
    
    
    def _construct_module_func(self, step_module: StepModule) -> Any:
        """
        Construct a function for the module execution.
        """
        mod_type = (step_module.type or "").lower()

        if mod_type == "human_input":
            # No-arg function that returns a prompt/description
            @observe(name=f"human_input_{step_module.name}")
            def _run() -> str:
                # Prefer 'description' from args.value if present, else step_module.description
                desc_spec = (step_module.args or {}).get("description") if isinstance(step_module.args, dict) else None
                arg_desc = (desc_spec or {}).get("value") if isinstance(desc_spec, dict) else None
                return str(arg_desc or step_module.description or "Human input required.")
            return _run

        if mod_type == "llm_call":
            @observe(name=f"llm_call_{step_module.name}")
            def _run(**kwargs):
                payload = dict(kwargs)
                result = self.module_client.execute_module(step_module.name, payload=payload)
                return self._apply_response_mapping(result, step_module.response_mapping)
            return _run

        # You can add more types here: http_call, tool_call, python_callable, etc.
        raise ValueError(f"Unsupported step module type: {step_module.type!r}")
            
    @observe(name="construct_module_tool")
    @graph_builder_exception_handler("Failed to construct module tool")
    def _construct_module_tool(self, workflow_name: str, step_module: StepModule) -> StructuredTool:
        """Construct a module tool with proper error handling."""
        try:
            ArgsSchema = self._build_args_schema_from_step(workflow_name, step_module)
            _run = self._construct_module_func(step_module)

            decor_workflow_name = "_".join(workflow_name.lower().split(" "))
            decor_step_name = "_".join(step_module.name.lower().split(" "))

            return StructuredTool.from_function(
                name=f"{decor_workflow_name}-{decor_step_name}",
                description=step_module.description or "No description provided",
                func=_run,
                args_schema=ArgsSchema,
                return_direct=False,
                # infer_schema=False,  # uncomment if you hit inference shenanigans
            )
        except Exception as e:
            logger.error(f"Error during tool construction for {step_module.name}: {e}")
            raise
    
    @observe(name="construct_agent_toolset")
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
        
        logger.info(f"Constructed tools from workflows: ", tools)    
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
            prompt = self.langfuse_client.get_prompt(self.PROMPT_PRIMARY_AGENT_CONSTRUCTION)
            if not prompt:
                raise PromptNotFoundError(f"Prompt '{self.PROMPT_AGENT_CONSTRUCTION}' not found in Langfuse.")
            compiled_prompt = prompt.compile(prompt=agent_config.instruction or "No instruction provided")
            return compiled_prompt
        else:
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

    def _construct_llm(self, agent_config: AgentConfig) -> Any:
        """
        Initialize the chat model based on the agent configuration.
        """
        return init_chat_model(
            model=agent_config.model,
            stream_usage=agent_config.stream_usage,
            api_key=agent_config.get_decrypted_api_key(),
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
        tools = self._construct_agent_toolset(agent_config.workflows) 
        if not tools:
            logger.warning("No tools were successfully constructed for the agent")

        # Get prompt
        prompt = self._get_agent_construction_prompt(agent_config)

        # Create the react agent
        return create_react_agent(llm, tools=tools, prompt=prompt, name=agent_config.name)

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

        successfully_added = []
        
        for agent_config in agents:
            try:
                agent = self.build_agent(agent_config)
                successfully_added.append(agent)

                logger.info(f"Successfully added agent '{agent_config.name}' to graph")
                
            except Exception as e:
                logger.error(f"Failed to build agent '{agent_config.name}': {e}")
                # Continue with other agents rather than failing completely
                continue

        primary_agent = create_supervisor(
            agents=successfully_added,
            model=primary_llm,
            prompt=primary_prompt,
        )

        return primary_agent.compile(
            checkpointer=self.checkpointer,
            store=self.store,
        )

