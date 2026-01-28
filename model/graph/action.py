from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class Action(str, Enum):
    """Available actions for the action API."""
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class InterruptObject(BaseModel):
    """Object representing an interrupt action."""
    action_name: str = Field(..., description="Name of the action to be performed")
    message: Optional[str] = Field(None, description="Optional message for the interrupt")
    requires_signature: bool = Field(False, description="Flag indicating if signature is required")
    transaction: Optional[dict] = Field(None, description="Transaction details (for blockchain transactions)")
    
class ActionMetadata(BaseModel):
    """Metadata for an action."""
    message: Optional[str] = None
    tx_hash: Optional[str] = None
    
class ActionRequest(BaseModel):
    """Request model for action API."""
    thread_id: str = Field(..., description="ID of the conversation thread")
    action_name: str = Field("", description="Name of the action to be performed (if empty, will match any pending action)")
    action: Action = Field(..., description="Action to be performed")
    metadata: ActionMetadata = Field(
        default_factory=ActionMetadata,
        description="Additional metadata for the action request"
    )
    