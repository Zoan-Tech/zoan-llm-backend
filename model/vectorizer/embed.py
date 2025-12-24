from pydantic import BaseModel, Field
from typing import Optional

# ============================================================================
# Request Models
# ============================================================================
class EmbedRequest(BaseModel):
    """Request model for embedding API."""
    text: str = Field(
        ...,
        description="Text to be embedded",
    )
    image: Optional[str] = Field(
        None,
        description="Image URL to be embedded",
    )
    
# ============================================================================
# Response Models
# ============================================================================
class EmbedResponse(BaseModel):
    """Response model for embedding API."""
    text: list[float] = Field(
        ...,
        description="List of embeddings for the input texts",
    )
    
    image: Optional[list[float]] = Field(
        None,
        description="List of embeddings for the input images",
    )