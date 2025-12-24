from fastapi.responses import JSONResponse

from fastapi import APIRouter

from handler.utils import APIStatus

router = APIRouter()
    
@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint to verify the service is running.
    Returns a simple status message.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": APIStatus.OK,
            "data": [],
            "message": "Media Description Service is running"
        }
    )