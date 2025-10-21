from langchain.chat_models import init_chat_model
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
        
    def _extra_openai_kwargs(self, model_name) -> dict:
        kwargs = {
            "use_responses_api": True,
            "output_version":"responses/v1",
            # "use_previous_response_id": True
        }
        
        if 'gpt-5-mini' not in model_name:
            kwargs["reasoning"] = {
                "effort": "low",
                "summary": "detailed",
            }
        
        return kwargs
        
    def _extra_anthropic_kwargs(self) -> dict:
        return {}
    
    def _audit_chat_model_config(self, model_name: str):
        kwargs = {}
        
        provider = self._get_provider(model_name)
        self._ensure_provider_api_key(provider)
        
        if provider == LLMProvider.OPENAI:
            kwargs.update(self._extra_openai_kwargs(model_name))
        
        elif provider == LLMProvider.ANTHROPIC:
            kwargs.update(self._extra_anthropic_kwargs())
        
        return kwargs
            
            
    def _construct_llm_model(self, agent_config: AgentConfig):
        extra_kwargs = self._audit_chat_model_config(agent_config.model)
        return init_chat_model(
            model=agent_config.model,
            stream_usage=agent_config.stream_usage,
            timeout=120,
            **agent_config.model_kwargs.model_dump(exclude_none=True),
            **extra_kwargs,
        )