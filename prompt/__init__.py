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
  
  def close(self):
    """Close Langfuse client connection"""
    try:
      if hasattr(self, '_client') and self._client:
        self._client.close()
      elif hasattr(self, 'client') and self.client:
        self.client.close()
      # Call parent flush to ensure all data is sent
      if hasattr(self, 'flush'):
        self.flush()
    except Exception as e:
      print(f"Warning: Error closing Langfuse client: {e}")
  
  def __enter__(self):
    return self
  
  def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()

DEFAULT_PROMPT_MANAGER = LangfusePromptManager(
    host=os.environ.get(SecretEnum.LANGFUSE_HOST.value),
    public_key=os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value),
    secret_key=os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value),
)