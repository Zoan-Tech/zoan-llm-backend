from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from model import CompletionRequest
from action import completion_action

router = APIRouter()

@router.post("/completion/stream")
async def create_completion_stream(request: CompletionRequest):
    """Create a streaming completion response.

    Args:
        request (CompletionRequest): The request model containing parameters for completion.

    Returns:
        StreamingResponse: A streaming response with the completion data.
    """
    
    return StreamingResponse(
        completion_action.create_completion(**request.model_dump()),
        media_type="application/json"
    )

@router.delete("/completion/cache/{conversation_id}")
async def clear_conversation_cache(conversation_id: str) -> Dict[str, Any]:
    """Clear cached compiled graph for a specific conversation.

    Args:
        conversation_id (str): The conversation ID to clear cache for.

    Returns:
        Dict[str, Any]: Status of the cache clearing operation.
    """
    cleared = completion_action.clear_conversation_cache(conversation_id)
    return {
        "success": cleared,
        "message": f"Cache cleared for conversation {conversation_id}" if cleared else f"No cache found for conversation {conversation_id}"
    }

@router.delete("/completion/cache")
async def clear_all_cache() -> Dict[str, str]:
    """Clear all cached compiled graphs and conversation mappings.

    Returns:
        Dict[str, str]: Confirmation message.
    """
    completion_action.clear_all_cache()
    return {"message": "All caches cleared successfully"}

@router.post("/completion/cache/cleanup")
async def cleanup_expired_cache() -> Dict[str, Any]:
    """Manually trigger cleanup of expired cache entries.

    Returns:
        Dict[str, Any]: Number of expired entries removed and cleanup status.
    """
    removed_count = completion_action.force_cleanup_expired_cache()
    return {
        "message": "Expired cache cleanup completed",
        "removed_entries": removed_count
    }

@router.get("/completion/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the current cache state.

    Returns:
        Dict[str, Any]: Cache statistics including counts and cached items.
    """
    return completion_action.get_cache_stats()