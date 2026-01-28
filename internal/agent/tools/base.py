"""
Base tools and utilities for built-in agents.
Includes reusable search tool for RAG with multimodal support.
"""
import base64
import mimetypes
from typing import Annotated, Literal, Optional

import httpx
from qdrant_client.http import models as qm

from langchain.tools import InjectedToolCallId
from langchain.messages import HumanMessage, ToolMessage
from langchain_core.runnables.config import ensure_config
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import Config
from config.logging import get_logger
from utils.model import Model
from external.qdrant.collection.library import service as qdrant_library_service
from external.qdrant.collection.messages import service as qdrant_messages_service
from utils.const.multimodal import PAGINATION_OFFSET_MULTIPLIER

TEXT_EMBEDDING_MODEL = Model.openai_text_embedding_3_small

logger = get_logger()


class BuiltinToolName:
    WEB_SEARCH = "web_search"

class ProviderBuiltInTool:
    OPENAI = {
        BuiltinToolName.WEB_SEARCH: {
            "type": "web_search"
        },
    }
    
    ANTHROPIC = {
        BuiltinToolName.WEB_SEARCH: {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5
        },
    }


# ============================================================================
# Filter Builders
# ============================================================================
def _build_field_condition(key: str, value: str, match_type: str = "text") -> qm.FieldCondition:
    """Build a Qdrant field condition based on match type."""
    if match_type == "text":
        return qm.FieldCondition(key=key, match=qm.MatchTextAny(text_any=value))
    elif match_type == "any":
        return qm.FieldCondition(key=key, match=qm.MatchAny(any=value))
    else:
        raise ValueError(f"Unsupported match type: {match_type}")


def get_library_filter(
    user_id: str,
    filter: Optional[dict] = None
) -> qm.Filter:
    """Construct Qdrant filter for library search.
    
    Args:
        user_id: User ID for ownership filtering
        filter: Optional filters for object_key or mimetype
    
    Returns:
        Qdrant filter with must and optional should conditions
    """
    filter_ = qm.Filter(
        must=[_build_field_condition("owner", [user_id, "public"], match_type="any")]
    )
    
    if not filter:
        return filter_
    
    should_conditions = []
    supported_keys = {'object_key', 'mimetype'}
    
    for key, value in filter.items():
        if key in supported_keys:
            should_conditions.append(_build_field_condition(key, value))
    
    if should_conditions:
        filter_.should = should_conditions
    
    return filter_


def get_messages_filter(
    user_id: str,
    conversation_id: str,
    filter: Optional[dict] = None
) -> qm.Filter:
    """Construct Qdrant filter for messages/documents search.
    
    Args:
        user_id: User ID for filtering
        conversation_id: Conversation ID for filtering
        filter: Optional additional filters
    
    Returns:
        Qdrant filter with all must conditions
    """
    must_conditions = [
        _build_field_condition("user_id", user_id),
        _build_field_condition("conversation_id", conversation_id)
    ]
    
    if filter:
        for key, value in filter.items():
            must_conditions.append(_build_field_condition(key, value))
    
    return qm.Filter(must=must_conditions)


# ============================================================================
# Result Formatters
# ============================================================================
def _format_search_results(results: list, source: str) -> list[str]:
    """Format search results into readable text.
    
    Args:
        results: List of Qdrant query results
        source: Source type ('library' or 'messages')
    
    Returns:
        List of formatted result strings
    """
    formatted_results = []
    
    for idx, result in enumerate(results, start=1):
        if source == "library":
            bucket = result.payload.get("bucket", "unknown-bucket")
            object_key = result.payload.get("object_key", "unknown-object")
            url = f"{Config.MINIO_BROWSER_URL}/{bucket}/{object_key}"
        elif source == "messages":
            url = result.payload.get("attachment_url", "unknown-document")
        else:
            url = "unknown-source"
            
        formatted_results.append(
            f"{idx}. URL: {url}\nScore: {result.score:.4f}\n"
        )
    
    return formatted_results


# ============================================================================
# Universal Search Tool - RAG with Multimodal Support
# ============================================================================

@tool
def search_knowledge_base(
    query: Annotated[str, "The search query to find relevant content"],
    source: Annotated[Literal["library", "messages"], "Search from which collection: 'library' for public assets and user-owned game specs, themes, features; 'documents' for user's uploaded documents in current conversation"],
    filter: Annotated[Optional[dict], "Optional filter in JSON format. For library: {'object_key': 'path', 'mimetype': 'image/png'}. For documents: {'attachment_url': 'file.pdf'}"],
    limit: Annotated[int, "Maximum number of results to retrieve (default: 5)"],
    offset: Annotated[int, "The offset for pagination, starting from 0"],
    runtime: ToolRuntime,
) -> Command:
    """
    Universal search tool for finding relevant content across library and uploaded documents.
    Handles multimodal content (text + images) and returns results with rich context.
    
    **Sources:**
    - library: Public assets and user-owned game specs, themes, features
    - messages: User's uploaded documents in the current conversation
    
    **Filters:**
    Different sources support different filter keys:
    Library filters:
    - object_key: Filter by file name/path (partial matching)
    - mimetype: Filter by MIME type like 'image/png', 'text/javascript' (exact matching)
    
    Messages filters:
    - user_id: Filter by user ID
    - conversation_id: Filter by conversation ID
    - attachment_url: Filter by specific document URL/filename (text matching)
    - chunk_index: Filter by specific chunk index (exact matching)
    
    Document filters:
    - attachment_url: Filter by specific document URL/filename (text matching)
    
    **Returns:**
    Rich multimodal results with text and images automatically injected into conversation.
    """
    try:
        config = ensure_config()
        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id")
        conversation_id = configurable.get("thread_id")
        
        if not user_id:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content="Error: Missing user_id in configuration",
                    )
                ]
            })
        
        # Generate query embedding
        text_vector = TEXT_EMBEDDING_MODEL.embed_query(query)
        
        # Execute search based on source
        if source == "library":
            filter_ = get_library_filter(user_id, filter)
            results = qdrant_library_service.client.query_points(
                collection_name=source,
                query=text_vector,
                using="text",
                query_filter=filter_,
                limit=limit,
                offset=offset * PAGINATION_OFFSET_MULTIPLIER,
            ).points
        elif source == "messages":
            if not conversation_id:
                return Command(update={
                    "messages": [
                        ToolMessage(
                            content="Error: Missing conversation_id for messages search",
                        )
                    ]
                })
            filter_ = get_messages_filter(user_id, conversation_id, filter)
            results = qdrant_messages_service.client.query_points(
                collection_name=source,
                query=text_vector,
                using="text",
                query_filter=filter_,
                limit=limit,
                offset=offset * PAGINATION_OFFSET_MULTIPLIER,
            ).points
        else:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Error: Unsupported source '{source}'",
                    )
                ]
            })
        
        # Format results
        if not results:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content="No results found matching your query.",
                    )
                ]
            })
        
        logger.info(f"[search_knowledge_base] Retrieved: {results}")
        formatted_results = _format_search_results(results, source)
        
        return Command(update={
            "messages": [
                ToolMessage(
                    content="Search Results:\n" + "\n".join(formatted_results),
                )
            ]
        })
    except Exception as e:
        logger.error(f"[search_knowledge_base] Error during search: {str(e)}")
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"Error: Failed to execute search - {str(e)}",
                )
            ]
        })
    
def _determine_mime_type(response: httpx.Response, url: str) -> Optional[str]:
    """Determine MIME type from response headers or URL.
    
    Args:
        response: HTTP response object
        url: Original URL
    
    Returns:
        MIME type string or None
    """
    mime_type = response.headers.get('content-type', '').split(';')[0].strip()
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(url)
    return mime_type


@tool
def read_url(
    url: Annotated[str, "URL to read content from (supports images)"],
    runtime: ToolRuntime,
) -> Command:
    """
    Read content from a specified URL (supports images).
    
    Args:
        url: Full URL to fetch content from (e.g., "https://example.com/image.png")
    
    Returns:
        Command with content from the URL - images are embedded as base64,
        text content is returned as string.
    """
    try:
        # Fetch content from URL
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        
        # Determine mimetype
        mime_type = _determine_mime_type(response, url)
        
        # Handle images
        if mime_type and mime_type.startswith("image/"):
            encoded_image = base64.b64encode(response.content).decode('utf-8')
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Successfully read image from URL: {url}",
                    ),
                    HumanMessage(
                        content=[
                            {
                                "type": "image",
                                "base64": encoded_image,
                                "mime_type": mime_type
                            },
                        ]
                    )
                ]
            })
        
        # Handle unsupported content types
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"Unsupported content type: {mime_type or 'unknown'}",
                ),
            ]
        })
                
    except httpx.HTTPError as e:
        logger.error(f"[read_url] HTTP error fetching {url}: {str(e)}")
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"Failed to fetch URL: {str(e)}",
                ),
            ]
        })
    except Exception as e:
        logger.error(f"[read_url] Unexpected error reading URL {url}: {str(e)}")
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"Error: {str(e)}",
                ),
            ]
        })