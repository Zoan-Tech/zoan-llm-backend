from fastapi import APIRouter
from fastapi.responses import StreamingResponse

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