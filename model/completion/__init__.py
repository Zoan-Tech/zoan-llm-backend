from typing import Any, List, Optional

from pydantic import BaseModel, Field

from model.completion.agent import (
    AgentConfig,
    AgentWorkflow,
    StepModule,
    ModelKwargs,
    AgentKYA,
)

from model.completion.enums import (
    ChunkType,
    StreamingStatus,
)

__all__ = [
    "Attachment",
    "Metadata",
    "CompletionRequest",
    "ResponseMetadata",
    "ChunkContent",
    "StreamingChunk",
    "ChunkType",
    "StreamingStatus",
]

# ============================================================================
# Request Models
# ============================================================================

class Attachment(BaseModel):
    """Model representing a file attachment in a message."""
    url: str = Field(..., description="URL of the attachment")
    file_name: str = Field(..., description="Name of the file")
    mime_type: str = Field(..., description="MIME type of the attachment")
    file_size: str = Field(..., description="Size of the file in bytes")
    type: str = Field(..., description="Type of the attachment")


class Metadata(BaseModel):
    """Metadata associated with a completion request."""
    console_logs: str = Field("", description="Console logs associated with the request")
    attachments: Optional[List[Attachment]] = Field(
        default=None,
        description="List of attachments associated with the message"
    )
    web_search: bool = Field(
        False,
        description="Flag indicating if web search is enabled for this request"
    )
    
    command: Optional[str] = Field(
        None,
        description="Optional command to be executed"
    )
    
    


class CompletionRequest(BaseModel):
    """Request model for completion API."""
    user_id: str = Field(..., description="ID of the user making the request")
    conversation_id: str = Field(..., description="ID of the conversation")
    message: str = Field(..., description="Question to ask the model")
    agents: List[AgentConfig] = Field(
        ...,
        description="List of agent configurations to use for the completion"
    )
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="Additional metadata for the completion request"
    )


# ============================================================================
# Response Models
# ============================================================================

class ResponseMetadata(BaseModel):
    """Metadata about the completion response."""
    status: str = Field(
        ...,
        description="Status of the response",
        json_schema_extra={"json": "status"}
    )


class ChunkContent(BaseModel):
    """Content within a streaming chunk."""
    type: str = Field(
        ...,
        description="Type of the content",
        json_schema_extra={"json": "type"}
    )
    value: Any = Field(
        ...,
        description="Text content",
        json_schema_extra={"json": "value"}
    )
    agent: str = Field(
        ...,
        description="Agent identifier",
        json_schema_extra={"json": "agent"}
    )
    index: int = Field(
        ...,
        description="Index of the content",
        json_schema_extra={"json": "index"}
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata",
        json_schema_extra={"json": "metadata"}
    )


class StreamingChunk(BaseModel):
    """Model representing a streaming response chunk."""
    content: List[ChunkContent] = Field(
        [],
        description="List of content strings in the chunk"
    )
    response_metadata: ResponseMetadata = Field(
        ...,
        description="Metadata about the response"
    )