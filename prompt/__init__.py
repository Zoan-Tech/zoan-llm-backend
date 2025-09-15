import os
from abc import ABC
from langfuse import Langfuse
from utils.enums import *

class BasePromptManager(ABC):
  """
  Abstract base class for monitoring graph operations.
  """
  
class LangfusePromptManager(BasePromptManager, Langfuse):
  """
  Concrete implementation of BaseMonitor using Langfuse.
  """
  
DEFAULT_PROMPT_MANAGER = LangfusePromptManager(
    host=os.environ.get(SecretEnum.LANGFUSE_HOST.value),
    public_key=os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value),
    secret_key=os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value),
)