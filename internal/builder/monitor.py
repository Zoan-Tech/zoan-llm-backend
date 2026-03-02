from abc import ABC
from langfuse import Langfuse
from utils.enums import *
from config import Config

class BaseMonitor(ABC):
  """
  Abstract base class for monitoring graph operations.
  """
  
class LangfuseMonitor(BaseMonitor, Langfuse):
  """
  Concrete implementation of BaseMonitor using Langfuse.
  """
  
DEFAULT_MONITOR = LangfuseMonitor(
  host=Config.LANGFUSE_HOST,
  public_key=Config.LANGFUSE_PUBLIC_KEY,
  secret_key=Config.LANGFUSE_SECRET_KEY,
)