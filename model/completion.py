from typing import Optional
from pydantic import BaseModel, Field

class CompletionRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user making the request")
    conversation_id: str = Field(..., description="ID of the conversation")
    description: str = Field("", description="Agent description")
    prompt: str = Field("", description="Agent's system prompt")
    message: str = Field(..., description="Question to ask the model")
    model: str = Field("", description="Model name")
    model_token: str = Field("", description="Model token for authentication")
    response_format: Optional[dict] = Field(None, description="Response format for the model")
    model_kwargs: dict = Field({}, description="Model's extra configuration")