from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from api.utils import APIStatus

router = APIRouter()
    
@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint to verify the service is running.
    Returns a simple status message.
    """
    return {
        "status": APIStatus.OK,
        "message": "Service is running"
    }