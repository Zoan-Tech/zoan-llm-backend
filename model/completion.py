from typing import Optional
from pydantic import BaseModel, Field, field_validator

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

    @field_validator("response_format", mode="before")
    def validate_response_format(cls, value):
        """Ensure response_format is a dictionary or None."""
        if not isinstance(value, dict):
            raise ValueError("response_format must be a dictionary or None")
        if value.get("type") == "text":
            return None
        return value