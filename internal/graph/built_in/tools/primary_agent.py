"""
Tools for the Primary Agent.
"""
import httpx, base64
from typing import Annotated
import mimetypes
from config import Config
from langchain_core.runnables.config import ensure_config
from langchain.tools import BaseTool, ToolRuntime, tool
from langchain.tools import InjectedToolCallId
from langgraph.types import Command

from config.logging import get_logger
from action.webhook_client.chat_title import chat_title as chat_title_webhook_client
from langchain_core.messages import HumanMessage, ToolMessage

from services.qdrant_library_client import qm, qdrant_library_client
from internal.vectorizer.base import TEXT_EMBEDDING_MODEL

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
            update={**runtime.state, "messages": handoff_messages},
        )
    
    handoff_to_agent.metadata = {METADATA_KEY_HANDOFF_DESTINATION: agent_name}
    return handoff_to_agent

@tool
def search_knowledge_hub(
    query: Annotated[str, "The search query, related to game specifications, features, or themes"],
    offset: Annotated[int, "The offset for pagination, starting from 0, corresponds to the number of times the search has been performed."],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Search the library for relevant game specification/game feature or game themes/assets.
    
    Returns search results with text content and image URLs that will be automatically 
    injected into the conversation for visual analysis.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id", None)
    
    filter_ = qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=[user_id, "public"])
            )
        ]
    ) if user_id else qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=["public"])
            )
        ]
    )
    
    text_vector = TEXT_EMBEDDING_MODEL.embed_query(query)
        
    results = qdrant_library_client.client.search(
        collection_name=qdrant_library_client.collection_name,
        query_vector=("text", text_vector),
        query_filter=filter_,
        limit=5,
        offset=offset * 10,
    )
    
    # Collect image URLs from results
    human_messages = []
    
    for idx, result in enumerate(results):
        try:
            bucket = result.payload.get("bucket")
            object_key = result.payload.get("object_key")
            
            url = f"{Config.MINIO_BROWSER_URL}/{bucket}/{object_key}"
            mime_type = result.payload.get("mimetype")
            
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(url)
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            
            encoded_image = base64.b64encode(response.content).decode("utf-8")  # Fixed variable name
            description = result.payload.get("description", "No description available.")
            human_messages.append(HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"Image: {object_key} {description}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }
                    }
                ]
            ))
        except Exception as e:
            logger.error(f"[search_knowledge_hub] Error processing search result: {str(e)}", exc_info=True)
            continue
        
    messsages = [
        ToolMessage(
            content=f"Found {len(human_messages)} results for query: '{query}'",
            tool_call_id=tool_call_id
        )
    ] + human_messages
    
    # Return structured data with both text and image URLs
    return Command(update={
        "messages": messsages
    })