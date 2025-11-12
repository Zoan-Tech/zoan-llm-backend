from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1,  # <-- Super slow! We can only make a request once every 10 seconds!!
    check_every_n_seconds=0.1,  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=10,  # Controls the maximum burst size.
)
from langgraph_supervisor import create_supervisor

from model import AgentConfig
from config import Config
from utils.exception_handler import AgentConfigurationError

class LLMProvider:
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class ChatModel:
    def _ensure_provider_api_key(self, provider: LLMProvider) -> None:
        """Ensure the API key for the model provider is set in environment variables."""
        # Currently only OpenAI is supported
        if provider == LLMProvider.OPENAI:
            if not Config.OPENAI_API_KEY:
                raise AgentConfigurationError("OPENAI_API_KEY environment variable is not set")
        elif provider == LLMProvider.ANTHROPIC:
            if not Config.ANTHROPIC_API_KEY:
                raise AgentConfigurationError("ANTHROPIC_API_KEY environment variable is not set")
        else:
            raise AgentConfigurationError(f"Unsupported LLM provider: {provider}")
            
    def _get_provider(self, model_name: str) -> LLMProvider:
        if 'gpt-' in model_name or model_name.startswith("openai") or model_name.startswith("azure"):
            return LLMProvider.OPENAI
        elif 'claude-' in model_name or model_name.startswith("anthropic"):
            return LLMProvider.ANTHROPIC
        else:
            raise ValueError(f"Unsupported model name: {model_name}")
        
    def _extra_openai_kwargs(self, is_primary: bool) -> dict:
        kwargs = {
            "use_responses_api": True,
            "output_version":"responses/v1",
            # "use_previous_response_id": True
        }
        
        if not is_primary:
            kwargs["reasoning"] = {
                "effort": "high",
                "summary": "detailed",
            }
        else:
            kwargs["reasoning"] = None

        return kwargs
        
    def _extra_anthropic_kwargs(self, is_primary: bool) -> dict:
        return {}
    
    def _audit_chat_model_config(self, model_name: str, is_primary: bool = False) -> dict:
        kwargs = {}
        
        provider = self._get_provider(model_name)
        self._ensure_provider_api_key(provider)
        
        if provider == LLMProvider.OPENAI:
            kwargs.update(self._extra_openai_kwargs(is_primary))
        
        elif provider == LLMProvider.ANTHROPIC:
            kwargs.update(self._extra_anthropic_kwargs(is_primary))
        
        return kwargs
            
            
    def _construct_llm_model(self, agent_config: AgentConfig):
        extra_kwargs = self._audit_chat_model_config(agent_config.model, agent_config.is_primary)
        return init_chat_model(
            model=agent_config.model,
            stream_usage=agent_config.stream_usage,
            timeout=120,
            max_retries=3,
            rate_limiter=rate_limiter,
            **agent_config.model_kwargs.model_dump(exclude_none=True, include={"max_tokens"}),
            **extra_kwargs,
        )