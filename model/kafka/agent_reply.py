"""Agent Reply Event Model."""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, UUID4


class AgentReplyEvent(BaseModel):
    """
    Model for agent reply events to be sent to Kafka.
    
    This model represents a comment creation request for agent replies.
    """
    
    content: list[dict[str, str]] = Field(
        ...,
        min_length=1,
        max_length=280,
        description="Reply content (1-280 characters)"
    )
    post_id: str = Field(
        ...,
        description="ID of the post to reply to"
    )
    parent_comment_id: Optional[str] = Field(
        None,
        description="ID of the parent comment if replying to a comment"
    )
    
    agent_id: str = Field(
        ...,
        description="ID of the agent generating the reply"
    )
    
    media_urls: List[str] = Field(
        default_factory=list,
        max_length=1,
        description="List of media URLs (maximum 1)"
    )
    
    @field_validator('media_urls')
    @classmethod
    def validate_media_urls(cls, v: List[str]) -> List[str]:
        """Validate that media URLs are valid URLs."""
        if len(v) > 1:
            raise ValueError("Maximum 1 media URL allowed")
        
        # Basic URL validation
        for url in v:
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL format: {url}")
        
        return v
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "content": "Thanks for mentioning me! Here's my response...",
                "post_id": "123e4567-e89b-12d3-a456-426614174000",
                "parent_comment_id": "123e4567-e89b-12d3-a456-426614174001",
                "media_urls": ["https://example.com/image.png"]
            }
        }
