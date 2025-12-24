from pydantic import BaseModel, Field
from utils.model import Model

# ============================================================================
# Request Models
# ============================================================================

class MediaDescriptionRequest(BaseModel):
    """Request model for media description API."""
    model: str = Field(
        Model.openai_gpt_5_mini,
        description="Model to use for media description",
    )
    medias: list[str] = Field(
        [],
        description="List of media urls to describe",
    )
    
# ============================================================================
# Response Models
# ============================================================================
class MediaDescriptionResponse(BaseModel):
    """Response model for media description API."""
    media: str = Field(
        ...,
        description="URL of the media",
        json_schema_extra={"json": "media"}
    )
    
    description: str = Field(
        ...,
        description="Generated description of the media",
        json_schema_extra={"json": "description"}
    )

class MediaDescriptionTaskResponse(BaseModel):
    """Model representing a media description generation task."""
    task_id: str = Field(
        ...,
        description="Unique identifier for the media description task",
        json_schema_extra={"json": "task_id"}
    )
    
    status: str = Field(
        ...,
        description="Current status of the media description task",
        json_schema_extra={"json": "status"}
    )
    
    created_at: str = Field(
        ...,
        description="Timestamp when the task was created",
        json_schema_extra={"json": "created_at"}
    )
    
    result: list[MediaDescriptionResponse] | None = Field(
        None,
        description="Generated media descriptions upon task completion",
        json_schema_extra={"json": "result"}
    )