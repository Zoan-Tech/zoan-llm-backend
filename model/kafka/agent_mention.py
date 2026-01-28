"""Agent Mention Event Model."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from model.completion import AgentConfig, Metadata


class AgentMentionEvent(BaseModel):
    """
    Model for agent mention events from Kafka.
    
    This model represents an event when an agent is mentioned in a post or comment.
    """
    
    id: str = Field(
        ...,
        description="Unique event ID"
    )
    content: str = Field(
        ...,
        description="Content that mentioned the agent"
    )
    post_id: str = Field(
        ...,
        description="ID of the post/comment"
    )
    comment_id: Optional[str] = Field(
        None,
        description="ID of the comment if this is a comment mention"
    )
    user_id: str = Field(
        ...,
        description="User who created the content"
    )
    agent_configs: list[AgentConfig] = Field(
        ...,
        description="Configuration of the mentioned agent"
    )
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="Additional context (language, visibility, etc.)"
    )
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "evt_123456",
                "content": "@zoanchat what's the weather today?",
                "post_id": "post_789",
                "comment_id": "comment_012",
                "user_id": "user_345",
                "agent_id": "zoanchat",
                "metadata": {
                    "language": "en",
                    "visibility": "public"
                }
            }
        }
