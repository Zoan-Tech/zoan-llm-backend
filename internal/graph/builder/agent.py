from typing import Any, Dict, Optional

from langchain.agents import create_agent

from langchain_core.tools import StructuredTool

from model import (
    AgentConfig,
    StepModule,
    AgentWorkflow,
)

from internal.graph.chat_model import ChatModel
from internal.graph.builder.tool import ToolBuilder
from internal.graph.builder.prompt import BasePromptManager

from utils.exception_handler import (
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

    @graph_builder_exception_handler("Failed to build agent")
    def build_agent(self, agent_config: AgentConfig):
        """
        Build a react agent using the provided agent configuration.
        """
        # Validate configuration first
        self._validate_agent_config(agent_config)
        
        # Initialize the chat model
        llm = self.chat_model._construct_llm_model(agent_config, is_primary=False)

        # Construct tools
        toolset = self._construct_agent_toolset(agent_config.workflows)
        
        # Create the react agent
        return create_agent(llm, tools=toolset, system_prompt=agent_config.system_prompt, name=_sanitize_name(agent_config.name.lower()))
