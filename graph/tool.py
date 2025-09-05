import logging
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, create_model
from langfuse import observe
from langchain_core.tools import StructuredTool
from langchain_core.runnables.config import RunnableConfig, ensure_config

from module.client import ModuleClient, ModType

from model import (
    StepModule,
)

from utils.helper import to_py_type, _spec_get, _sanitize_name

logger = logging.getLogger(__name__)

class ToolBuilder:
    def __init__(
        self,
        module_client: ModuleClient,
    ):
        self.module_client = module_client

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

    def _build_args_schema_from_step(self, step_module: StepModule) -> type[BaseModel]:
        """
        Build a Pydantic model for the arguments of a step module.
        """
        args_spec = step_module.args or {}
        model_name = f"{step_module.name}Args".replace(" ", "")
        
        if not args_spec:
            return create_model(model_name)  # no-arg tool

        fields = {}
        for arg_name, spec in args_spec.items():
            py_type = to_py_type(_spec_get(spec, "type", "str"))
            desc = _spec_get(spec, "description", None)
            default_val = _spec_get(spec, "value", None)
            
            default = default_val

            fields[arg_name] = (py_type, Field(default=default, description=desc))
        
        return create_model(model_name, **fields)

    def _build_human_input_tool(self, workflow_name: str, step_module: StepModule) -> StructuredTool:
        """Build a human input tool."""
        decor_workflow_name = _sanitize_name(workflow_name.lower())
        decor_step_name = _sanitize_name(step_module.name.lower())
        tool_name = f"{decor_workflow_name}_{decor_step_name}"

        def _run():
            args = _spec_get(step_module, "args", None)
            description = _spec_get(args, "description", None) if args else None
            value = _spec_get(description, "value", None) if args else None
            return str(value or "Human input required.")
    
        return StructuredTool.from_function(
            name=tool_name,
            description=step_module.description or "No description provided",
            func=_run,
            return_direct=False,
            # infer_schema=False,  # uncomment if you hit inference shenanigans
        )
    
    def _build_module_tool(self, workflow_name: str, step_module: StepModule) -> StructuredTool:
        """Build a module tool."""
        decor_workflow_name = _sanitize_name(workflow_name.lower())
        decor_step_name = _sanitize_name(step_module.name.lower())
        tool_name = f"{decor_workflow_name}_{decor_step_name}"

        ArgsSchema = self._build_args_schema_from_step(step_module)

        def _run(*, config: RunnableConfig, **kwargs):
            cfg: RunnableConfig = ensure_config(config)
            thread_id = (cfg.get("configurable") or {}).get("thread_id")

            payload = dict(kwargs)
            if thread_id:
                payload["thread_id"] = thread_id
            result = self.module_client.execute_module(decor_step_name, payload=payload)
            return self._apply_response_mapping(result, step_module.response_mapping)

        return StructuredTool.from_function(
            name=tool_name,
            description=step_module.description or "No description provided",
            func=_run,
            args_schema=ArgsSchema,
            return_direct=False,
            # infer_schema=False,  # uncomment if you hit inference shenanigans
        )

    @observe(name="construct_module_tool")
    def _construct_tool(self, workflow_name: str, step_module: StepModule) -> Optional[StructuredTool]:
        """Construct a module tool with proper error handling."""
        try:
            mod_type = (step_module.type or "").lower()

            # if mod_type == ModType.HUMAN_INPUT:
            #     return self._build_human_input_tool(workflow_name, step_module)
            # else:
            if mod_type != ModType.HUMAN_INPUT:
                return self._build_module_tool(workflow_name, step_module)
        except Exception as e:
            logger.error(f"Error during tool construction for {step_module.name}: {e}")
            raise