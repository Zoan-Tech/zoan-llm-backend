from fastapi.responses import JSONResponse
from fastapi import APIRouter
from model.graph import (
    ActionRequest
)

from action.completion.swarm import swarm_completion

router = APIRouter()

GRAPH_ACTION_PREFIX = '/graph/action'

@router.post(f"{GRAPH_ACTION_PREFIX}")
async def graph_action_handler(
    request: ActionRequest,
) -> JSONResponse:
    """
    Endpoint for graph action handling.
    """
    await swarm_completion.submit_decision(
        thread_id=request.thread_id,
        action_name=request.action_name,
        decision=request.action,
        metadata=request.metadata
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "OK",
            "data": [],
            "message": "Graph action handled successfully"
        }
    )