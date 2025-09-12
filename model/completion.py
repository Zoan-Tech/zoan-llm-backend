from pydantic import BaseModel, Field
from model.graph.builder import AgentConfig

class CompletionRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user making the request")
    conversation_id: str = Field(..., description="ID of the conversation")

    message: str = Field(..., description="Question to ask the model")

    agents: list[AgentConfig] = Field(
        ...,
        description="List of agent configurations to use for the completion"
    )
    
class ChunkContent(BaseModel):
    type: str = Field(..., description="Type of the content", json_schema_extra={"json": "type"})
    text: str = Field(..., description="Text content", json_schema_extra={"json": "text"})
    agent: str = Field(..., description="Agent identifier", json_schema_extra={"json": "agent"})
    index: float = Field(..., description="Index of the content", json_schema_extra={"json": "index"})
    url: str = Field(..., description="URL associated with the content", json_schema_extra={"json": "url"})
    
class ResponseMetadata(BaseModel):
    status: str = Field(..., description="Status of the response", json_schema_extra={"json": "status"})
    
class StreamingChunk(BaseModel):
    content: list[ChunkContent] = Field([], description="List of content strings in the chunk")
    response_metadata: ResponseMetadata = Field(..., description="Metadata about the response")