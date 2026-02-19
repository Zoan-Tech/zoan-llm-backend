"""
Wallet Agent - Handles token swaps and cross-chain bridging.
Supports multiple EVM chains with DEX swap and bridge functionality.
"""
from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.tools.wallet_agent import tools
from internal.agent.middleware.base import get_base_middleware
from model.completion import AgentConfig

logger = get_logger()


class WalletAgent(BaseInternalAgent):
    """
    Wallet Agent for managing token swaps and cross-chain bridging.
    
    This agent specializes in:
    - Swapping tokens on DEXs (Uniswap V2-compatible routers)
    - Bridging assets across EVM-compatible chains
    - Supporting multiple chains: Ethereum, Arbitrum, BSC, Polygon, Base, Optimism, Avalanche
    
    All transactions require user signature via interrupt flow.
    """
    SANITIZED_NAME = "wallet_agent"
    PROMPT_NAME = "wallet_agent_v1"
    
    def get_toolset(self) -> list:
        """
        Get the tools available for wallet operations.
        
        Returns:
            List of wallet tools including swap and bridge
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
        Create the Wallet Agent with LLM and tools.
        
        Args:
            agent_config: Configuration for the agent including model settings
            **kwargs: Additional arguments
        
        Returns:
            Configured agent ready for wallet operations
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
wallet_agent = WalletAgent()
