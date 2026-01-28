"""
CoinGecko Agent - Handles cryptocurrency market data and trends.
Provides global market insights, trending coins, and market cap analysis.
"""
from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.tools.coingecko_agent import (
    get_global_market_data,
    get_trending_coins,
)
from internal.agent.middleware.base import get_base_middleware
from model.completion import AgentConfig

logger = get_logger()


class CoinGeckoAgent(BaseInternalAgent):
    """
    CoinGecko Agent for fetching cryptocurrency market data.
    
    This agent specializes in:
    - Global cryptocurrency market trends and statistics
    - Trending coins and tokens (based on search activity)
    - Market capitalization rankings and changes
    - DeFi market overview
    - Price lookups for specific cryptocurrencies
    
    Data source: CoinGecko API (free tier)
    """
    SANITIZED_NAME = "coingecko_agent"
    PROMPT_NAME = "coingecko_agent_v1"
    
    def get_toolset(self) -> list:
        """
        Get the tools available for CoinGecko market data.
        
        Returns:
            List of market data tools for cryptocurrency analysis
        """
        base_tools = [
            get_global_market_data,
            get_trending_coins,
        ]
        return base_tools + self.handoff_tools
    
    def get_middleware(self) -> list:
        """Get middleware for the agent."""
        base_middleware = get_base_middleware()
        return base_middleware
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        """
        Create the CoinGecko Agent with LLM and tools.
        
        Args:
            agent_config: Configuration for the agent including model settings
            **kwargs: Additional arguments
        
        Returns:
            Configured agent ready for market data operations
        """
        self._prepare_handoff_tools(handoff_instructions=kwargs.get("handoff_instructions", {}))
            
        llm = self._construct_llm_model(agent_config)
        
        toolset = self.get_toolset()
        
        system_prompt = self.get_prompt()
        
        middleware = self.get_middleware()
        
        return create_agent(
            model=llm,
            tools=list(toolset),
            system_prompt=system_prompt,
            middleware=middleware,
            name=self.SANITIZED_NAME,
            checkpointer=kwargs.get("checkpointer"),
            store=kwargs.get("store"),
        )


# Export singleton instance
coingecko_agent = CoinGeckoAgent()
