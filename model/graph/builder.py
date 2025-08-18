from typing import Optional
from pydantic import BaseModel, Field, SecretStr
import os
from utils.helper import decrypt_token
from utils.enums import SecretEnum

class ModelKwargs(BaseModel):
    temperature: Optional[float] = Field(None, description="Sampling temperature for the model")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")
    top_p: Optional[float] = Field(None, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(0.0, description="Penalty for frequency of tokens")
    presence_penalty: float = Field(0.0, description="Penalty for presence of tokens")
    stop: Optional[list[str]] = Field(None, description="List of stop sequences for the model")

class StepModuleArgs(BaseModel):
    type: str = Field(..., description="Type of the argument")
    description: Optional[str] = Field(None, description="Description of the argument")
    value: Optional[str] = Field(None, description="Value of the argument")
    required: bool = Field(False, description="Whether the argument is required")
    end_user_input: bool = Field(False, description="Whether this argument requires end-user input", alias="end-user_input")

class StepModule(BaseModel):
    name: str = Field(..., description="Name of the step module")
    type: str = Field(..., description="Type of the step module")
    description: Optional[str] = Field(None, description="Description of the step module")
    args: Optional[dict[str, StepModuleArgs]] = Field(None, description="Arguments for the step module")
    response_mapping: Optional[dict] = Field(None, description="Mapping of response fields to step variables")

class AgentWorkflow(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for the agent workflow")
    name: str = Field(..., description="Name of the agent workflow")
    description: Optional[str] = Field(None, description="Description of the agent workflow")
    steps: list[StepModule] = Field(..., description="List of steps in the agent workflow")

class AgentConfig(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for the agent")
    name: str = Field(..., description="Name of the agent")
    
    model: str = Field(..., description="Model name")
    model_kwargs: ModelKwargs = Field(default_factory=ModelKwargs, description="Additional model configuration")
    
    api_key: SecretStr = Field(..., description="API key for the model")

    description: Optional[str] = Field(None, description="Description of the agent")
    instruction: Optional[str] = Field(None, description="Instruction for the agent")

    workflows: list[AgentWorkflow] = Field(..., description="List of agent workflows")
    
    stream_usage: bool = Field(True, description="Whether to stream usage")    
    def get_decrypted_api_key(self) -> str:
        """Decrypt the API key using the Fernet secret."""
        try:
            encrypted = self.api_key.get_secret_value()
            fernet_secret = os.environ.get(SecretEnum.FERNET_SECRET.value)
            if not fernet_secret:
                raise ValueError("FERNET_SECRET environment variable is not set")
            return decrypt_token(encrypted, fernet_secret)
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {e}") from e