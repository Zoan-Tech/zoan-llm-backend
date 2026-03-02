"""
Aster Trading Agent - Handles perpetual futures trading on Aster DEX.
Supports BNB Chain and Arbitrum with Simple Mode trading.
"""
from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.tools.aster_trading_agent import (
    open_market_trade,
    close_trade,
)   
from internal.agent.middleware.base import get_base_middleware
from model.completion import AgentConfig

logger = get_logger()


class AsterTradingAgent(BaseInternalAgent):
    """
    Aster Trading Agent for managing perpetual futures positions.
    
    This agent specializes in:
    - Opening long/short positions on BNB Chain and Arbitrum
    - Closing positions (full or partial)
    - Checking account balances and positions
    - Managing positions in Simple Mode (one position per symbol)
    
    Supported chains: BNB Chain, Arbitrum
    """
    SANITIZED_NAME = "aster_trading_agent"
    PROMPT_NAME = "aster_trading_agent_v1"
    
    def get_toolset(self) -> list:
        """
        Get the tools available for Aster DEX trading.
        
        Returns:
            List of trading tools including position management and account queries
        """
        base_tools = [
            open_market_trade,
            close_trade,
        ]
        return base_tools + self.handoff_tools
    
    def get_middleware(self) -> list:
        """Get middleware for the agent."""
        base_middleware = get_base_middleware()
        # No special middleware needed for now
        return base_middleware + [
            # trading_interrupt_middleware,
            # human_in_the_loop_middleware,
        ]
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        """
        Create the Aster Trading Agent with LLM and tools.
        
        Args:
            agent_config: Configuration for the agent including model settings
            **kwargs: Additional arguments (e.g., user_wallet_address)
        
        Returns:
            Configured agent ready for trading operations
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
aster_trading_agent = AsterTradingAgent()