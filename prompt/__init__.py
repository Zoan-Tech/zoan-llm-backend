from abc import ABC
from langfuse import Langfuse
from utils.enums import *
from config import Config

class BasePromptManager(ABC):
  """
  Abstract base class for monitoring graph operations.
  """
  
class LangfusePromptManager(BasePromptManager, Langfuse):
  """
  Concrete implementation of BaseMonitor using Langfuse.
  """
  
langfuse_prompt_manager = LangfusePromptManager(
    host=Config.LANGFUSE_HOST,
    public_key=Config.LANGFUSE_PUBLIC_KEY,
    secret_key=Config.LANGFUSE_SECRET_KEY,
)