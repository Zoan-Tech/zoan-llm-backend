from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from config.logging import get_logger

from model import CompletionRequest
from action.completion import completion_action

router = APIRouter()

logger = get_logger()

@router.post("/completion/stream")
async def create_completion_stream(request: CompletionRequest):
    """Create a streaming completion response.

    Args:
        request (CompletionRequest): The request model containing parameters for completion.

    Returns:
        StreamingResponse: A streaming response with the completion data.
    """
    return StreamingResponse(
        completion_action.create_completion(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            message=request.message,
            agents=request.agents,
            attachments=request.attachments,
            metadata=request.metadata
        ),
        media_type="application/json"
    )

@router.delete("/completion/cache")
async def clear_all_cache() -> Dict[str, str]:
    """Clear all cached compiled graphs.

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