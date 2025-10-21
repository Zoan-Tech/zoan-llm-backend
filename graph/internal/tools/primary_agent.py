"""
Tools for the Primary Agent.
"""
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.runnables.config import ensure_config

from config.logging import get_logger
from action.chat_title_generator import chat_title_generator

logger = get_logger()


@tool
def update_chat_title(
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
        success = chat_title_generator.update_title(
            conversation_id=conversation_id,
            title=title,
            auth_token=auth_token
        )
        
        if success:
            logger.info(f"[update_chat_title] Successfully updated title for {conversation_id} to '{title}'")
            return f"✅ Chat title updated to: {title}"
        else:
            logger.warning(f"[update_chat_title] Failed to update title for {conversation_id}")
            return "⚠️ Title update failed - please check logs"
            
    except Exception as e:
        logger.error(f"[update_chat_title] Error in tool execution: {str(e)}", exc_info=True)
        return f"❌ Error updating title: {str(e)}"

