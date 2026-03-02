"""
Hyperliquid Trading Agent - Handles perpetual futures trading on Hyperliquid testnet.
Supports market and limit orders for opening and closing positions.
"""
from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.tools.hyperliquid_trading_agent import tools
from internal.agent.middleware.base import get_base_middleware
from model.completion import AgentConfig
from config.prompt.kya_instruction import KYA_INSTRUCTIONS

logger = get_logger()


class HyperliquidTradingAgent(BaseInternalAgent):
    """
    Hyperliquid Trading Agent for managing perpetual futures positions on testnet.
    
    This agent specializes in:
    - Opening long/short positions with market or limit orders
    - Closing positions (full or partial)
    - Managing risk with stop loss and take profit orders
    - Trading on Hyperliquid testnet environment
    
    Supported operations:
    - Market orders for immediate execution
    - Limit orders for specific price targets
    - Stop loss and take profit management
    - Partial and full position closure
    """
    SANITIZED_NAME = "hyperliquid_trading_agent"
    PROMPT_NAME = "hyperliquid_trading_agent_v1"
    
    def get_toolset(self) -> list:
        """
        Get the tools available for Hyperliquid trading.
        
        Returns:
            List of trading tools for position management
        """
        return tools + self.handoff_tools
    
    def get_middleware(self) -> list:
        """
        Get middleware for the agent.
        
        Returns:
            List of middleware functions
        """
        base_middleware = get_base_middleware()
        return base_middleware
    
    def get_agent(self, agent_config: AgentConfig, **kwargs):
        """
        Create the Hyperliquid Trading Agent with LLM and tools.
        
        Args:
            agent_config: Configuration for the agent including model settings
            **kwargs: Additional arguments
        
        Returns:
            Configured agent ready for trading operations
        """
        self._prepare_handoff_tools(handoff_instructions=kwargs.get("handoff_instructions", {}))
            
        llm = self._construct_llm_model(agent_config)
        
        toolset = self.get_toolset()
        
        kya_instruction = KYA_INSTRUCTIONS.get("not_paired") if not agent_config.agent_kya else ""
        
        system_prompt = self.get_prompt(
            kya_instruction=kya_instruction
        )
        
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
hyperliquid_trading_agent = HyperliquidTradingAgent()
