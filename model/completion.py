from typing import Optional, List
from pydantic import BaseModel, Field
from model.graph.builder import AgentConfig

class Attachment(BaseModel):
    url: str = Field(..., description="URL of the attachment")
    mime_type: str = Field(..., description="MIME type of the attachment")
    
class Metadata(BaseModel):
    console_logs: str = Field("", description="Console logs associated with the request")

class CompletionRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user making the request")
    conversation_id: str = Field(..., description="ID of the conversation")

    message: str = Field(..., description="Question to ask the model")
    
    attachments: Optional[List[Attachment]] = Field(default=None, description="List of attachments associated with the message")

    agents: List[AgentConfig] = Field(
        ...,
        description="List of agent configurations to use for the completion"
    )
    
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="Additional metadata for the completion request"
    )
    
class ChunkContent(BaseModel):
    type: str = Field(..., description="Type of the content", json_schema_extra={"json": "type"})
    text: str = Field(..., description="Text content", json_schema_extra={"json": "text"})
    agent: str = Field(..., description="Agent identifier", json_schema_extra={"json": "agent"})
    index: float = Field(..., description="Index of the content", json_schema_extra={"json": "index"})
    url: str = Field(..., description="URL associated with the content", json_schema_extra={"json": "url"})
    game_version: str = Field(None, description="Game version identifier", json_schema_extra={"json": "game_version"})
    
class ResponseMetadata(BaseModel):
    status: str = Field(..., description="Status of the response", json_schema_extra={"json": "status"})
    
class StreamingChunk(BaseModel):
    content: List[ChunkContent] = Field([], description="List of content strings in the chunk")
    response_metadata: ResponseMetadata = Field(..., description="Metadata about the response")