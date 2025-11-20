from typing import Any

from langchain.agents.middleware import SummarizationMiddleware, before_model, AgentState
from langgraph.runtime import Runtime

from internal.graph.built_in.helper.context import inject_images_from_tool_results

@before_model
def extract_and_persist_images(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """
    Extract images once at supervisor level and persist them in state.
    This middleware runs before the supervisor's model call.
    """
    messages = state["messages"].copy()
    image_urls_context = runtime.context.get("image_urls", []) if runtime.context else []
    
    image_messages = inject_images_from_tool_results(messages, image_urls_context)
    new_messages = image_messages.get("messages", [])
    new_images = image_messages.get("images", [])
        
    state["messages"].extend(new_messages)
    
    if runtime.context is not None:
        runtime.context["image_urls"] = image_urls_context + new_images

def get_base_middleware(
    max_tokens_before_summary=10000,
    messages_to_keep=10,
    include_image_extraction=False,
) -> list:
    base_middleware = [
        SummarizationMiddleware(
            model="gpt-5-mini",
            max_tokens_before_summary=max_tokens_before_summary,  # Trigger summarization at 4000 tokens
            messages_to_keep=messages_to_keep,  # Keep last 20 messages after summary
        ),
    ]
    if include_image_extraction:
        base_middleware.append(extract_and_persist_images)
    
    return base_middleware