import os
from abc import ABC
from langfuse import Langfuse
from utils.enums import *

class BaseMonitor(ABC):
  """
  Abstract base class for monitoring graph operations.
  """
  
class LangfuseMonitor(BaseMonitor, Langfuse):
  """
  Concrete implementation of BaseMonitor using Langfuse.
  """
  
DEFAULT_MONITOR = LangfuseMonitor(
    host=os.environ.get(SecretEnum.LANGFUSE_HOST.value),
    public_key=os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value),
    secret_key=os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value),
)