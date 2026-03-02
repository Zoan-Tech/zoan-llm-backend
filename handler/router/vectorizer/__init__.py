from fastapi.responses import JSONResponse

from model.vectorizer import (
    EmbedRequest,
    EmbedResponse,
)
from fastapi import APIRouter

from handler.utils import APIStatus
from action.vectorizer.embed import Vectorizer

router = APIRouter()

VECTORIZER_PREFIX = "/vectorizer"

@router.post(f"{VECTORIZER_PREFIX}/embed")
async def vectorizer_embed(request: EmbedRequest) -> JSONResponse:
    """
    Endpoint for vectorizer embedding service.
    Generates embeddings for provided texts and images.
    """
    response: EmbedResponse = Vectorizer.embed(
        text=request.text,
        image_url=request.image
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "status": APIStatus.OK,
            "data": [response.model_dump()],
            "message": "Embeddings generated successfully"
        }
    )