from typing import Optional
from enum import Enum
from pydantic import SecretStr
from utils.secret_manager import secret_manager
from config import Config
import json

from pydantic import BaseModel, Field


# ============================================================================
# Model Configuration
# ============================================================================

class ModelKwargs(BaseModel):
    """Configuration parameters for model inference."""
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature for the model"
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate"
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling parameter"
    )
    # frequency_penalty: float = Field(0.0, description="Penalty for frequency of tokens")
    # presence_penalty: float = Field(0.0, description="Penalty for presence of tokens")
    stop: Optional[list[str]] = Field(
        None,
        description="List of stop sequences for the model"
    )


# ============================================================================
# Agent Workflow Components
# ============================================================================

class StepModuleArgs(BaseModel):
    """Arguments for a step module in an agent workflow."""
    type: str = Field(..., description="Type of the argument")
    description: Optional[str] = Field(None, description="Description of the argument")
    value: Optional[str] = Field(None, description="Value of the argument")
    required: bool = Field(False, description="Whether the argument is required")
    end_user_input: bool = Field(
        False,
        description="Whether this argument requires end-user input",
        alias="end-user_input"
    )


class StepModule(BaseModel):
    """A single step in an agent workflow."""
    name: str = Field(..., description="Name of the step module")
    type: str = Field(..., description="Type of the step module")
    description: Optional[str] = Field(None, description="Description of the step module")
    args: Optional[dict[str, StepModuleArgs]] = Field(
        None,
        description="Arguments for the step module"
    )
    response_mapping: Optional[dict] = Field(
        None,
        description="Mapping of response fields to step variables"
    )


class AgentWorkflow(BaseModel):
    """A workflow defining a sequence of steps for an agent to execute."""
    id: Optional[str] = Field(None, description="Unique identifier for the agent workflow")
    name: str = Field(..., description="Name of the agent workflow")
    description: Optional[str] = Field(None, description="Description of the agent workflow")
    steps: list[StepModule] = Field(..., description="List of steps in the agent workflow")


# ============================================================================
# Agent Configuration
# ============================================================================

class AgentType(str, Enum):
    """Type of the agent."""
    PRIMARY     = "primary"     # Supervisor/orchestrator
    GENERATOR   = "generator"   # Code/app generation
    INFO        = "info"        # QA, analysis, research
    INTEGRATION = "integration" # API calls, non-financial actions
    TRADING     = "trading"     # Web3 transactions, revenue-generating

class AgentKYA(BaseModel):
    """KYA for the agent."""
    wallet_address: str = Field(None, description="Wallet address")
    wallet_private_key: Optional[SecretStr] = Field(None, description="Wallet private key")
    api_key: Optional[SecretStr] = Field(None, description="API key")
    api_secret: Optional[SecretStr] = Field(None, description="API secret")

class AgentConfig(BaseModel):
    """Configuration for an agent including model settings and workflows."""
    id: Optional[str] = Field(None, description="Unique identifier for the agent")
    name: str = Field(..., description="Name of the agent")
    description: Optional[str] = Field(None, description="Description of the agent")
    instruction: Optional[str] = Field(None, description="Instruction for the agent")
    
    model: str = Field(..., description="Model name")
    model_kwargs: ModelKwargs = Field(
        default_factory=ModelKwargs,
        description="Additional model configuration"
    )

    type: AgentType = Field(..., description="Type of the agent")
    agent_kya: Optional[str] = Field(None, description="Agent key")
    
    is_enabled: bool = Field(..., description="Whether the agent is enabled")
    is_primary: bool = Field(..., description="Whether the agent is the primary agent")
    
    workflows: list[AgentWorkflow] = Field([], description="List of agent workflows")
    
    stream_usage: bool = Field(True, description="Whether to stream usage")
    
    def decrypt_fields(self) -> AgentKYA:
        """Decrypt sensitive fields using the secret manager."""
        if self.agent_kya:
            decrypted_kya = secret_manager.decrypt(self.agent_kya)
            # Parse JSON string to dict if needed
            if isinstance(decrypted_kya, str):
                decrypted_kya = json.loads(decrypted_kya)
                
            return AgentKYA(**decrypted_kya)