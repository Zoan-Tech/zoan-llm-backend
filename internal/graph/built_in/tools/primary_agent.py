"""
Tools for the Primary Agent.
"""
from typing import Annotated

from langchain.tools import BaseTool, ToolRuntime, tool
from langchain_core.runnables.config import ensure_config
from langgraph.types import Command

from action.webhook_client.chat_title import chat_title as chat_title_webhook_client
from config.logging import get_logger

logger = get_logger()

METADATA_KEY_HANDOFF_DESTINATION = "__handoff_destination"

@tool
def zoan_internal_update_chat_title(
    title: Annotated[str, "The chat title to set (concise, 3-7 words, descriptive of the conversation)"],
) -> str:
    """
    Update the chat title to help organize conversations.
    
    The Primary Agent should:
    1. Analyze the conversation context
    2. Generate a concise, descriptive title (3-7 words)
    3. Call this tool with the generated title
    
    Best used in early conversations (first 1-3 turns) or when the topic shifts significantly.
    
    Returns a message indicating whether the title was updated successfully.
    """
    try:
        config = ensure_config()
        configurable = config.get("configurable", {})
        
        conversation_id = configurable.get("thread_id", "default")
        auth_token = configurable.get("auth_token", "")
        
        if not title or not title.strip():
            logger.warning(f"[update_chat_title] Empty title provided for {conversation_id}")
            return "❌ Cannot update title: Title is empty"
        
        # Clean and validate the title
        title = title.strip().strip('"\'')
        
        if len(title) > 100:
            title = title[:97] + "..."
            logger.debug(f"[update_chat_title] Title truncated to 100 characters for {conversation_id}")
        
        # Update title via webhook
        success = chat_title_webhook_client.update_title(
            conversation_id=conversation_id,
            title=title,
            auth_token=auth_token
        )
        
        if success:
            return f"✅ Chat title updated to: {title}"
        else:
            logger.warning(f"[update_chat_title] Failed to update title for {conversation_id}")
            return "⚠️ Title update failed - please check logs"
            
    except Exception as e:
        logger.error(f"[update_chat_title] Error in tool execution: {str(e)}", exc_info=True)
        return f"❌ Error updating title: {str(e)}"


def create_handoff_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None,
) -> BaseTool:
    """Create a tool that handoffs to another agent using Command."""
    
    if name is None:
        name = f"transfer_to_{agent_name}"
    
    if description is None:
        description = f"Transfer control to '{agent_name}' agent for specialized help"
    
    @tool(name, description=description)
    def handoff_to_agent(runtime: ToolRuntime) -> Command:
        """Handoff to another agent."""
        # Return a Command to route to the target agent
        messages = runtime.state["messages"]
        handoff_messages = messages[:-1]

        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={
                **runtime.state,
                "messages": handoff_messages,
            },
        )
    
    handoff_to_agent.metadata = {METADATA_KEY_HANDOFF_DESTINATION: agent_name}
    return handoff_to_agent