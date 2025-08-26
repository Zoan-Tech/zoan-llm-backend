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
    
    use_conversation_cache: bool = Field(
        default=False,
        description="Whether to use conversation-based caching for compiled graphs"
    )