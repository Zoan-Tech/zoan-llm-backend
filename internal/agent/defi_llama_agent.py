"""
DefiLlama Agent - Advanced DeFi market intelligence powered by DefiLlama data.

Features:
- Market overview (TVL, trends)
- Liquidity rotation detection
- Fastest growing protocols
- Yield opportunity discovery
- Stablecoin liquidity signals
- Emerging narrative detection
"""

from langchain.agents import create_agent

from config.logging import get_logger
from internal.agent.base import BaseInternalAgent
from internal.agent.middleware.base import get_base_middleware
from model.completion import AgentConfig

from internal.agent.tools.defillama_agent import (
    get_defi_global_overview,
    get_chain_liquidity_flows,
    get_protocol_growth_ranked,
    get_top_yield_opportunities,
    get_stablecoin_liquidity_signals,
    detect_emerging_narratives,
    get_protocol_tvl_tracker,
    detect_early_tvl_spikes,
    get_dex_volume_analytics,
    get_bridge_crosschain_flows,
    get_protocol_health_score,
    detect_tvl_dump_risk,
    get_alpha_opportunities,
)

logger = get_logger()


class DefiLlamaAgent(BaseInternalAgent):
    """
    DefiLlama Agent for advanced DeFi market intelligence.

    This agent specializes in:
    - Global DeFi market overview (TVL, trends)
    - Liquidity rotation detection across chains
    - Fastest growing protocol rankings
    - Top yield farming opportunities
    - Stablecoin liquidity flow signals
    - Emerging DeFi narrative detection
    - Protocol TVL tracking (1h/24h/7d)
    - Early TVL spike detection
    - DEX volume analytics
    - Bridge/cross-chain flow data
    - Protocol health scoring
    - TVL dump risk alerts
    - Alpha opportunity scoring

    Data source: DefiLlama API
    """
    SANITIZED_NAME = "defi_llama_agent"
    PROMPT_NAME = "defi_llama_agent_v1"

    def get_toolset(self) -> list:
        base_tools = [
            get_defi_global_overview,
            get_chain_liquidity_flows,
            get_protocol_growth_ranked,
            get_top_yield_opportunities,
            get_stablecoin_liquidity_signals,
            detect_emerging_narratives,
            get_protocol_tvl_tracker,
            detect_early_tvl_spikes,
            get_dex_volume_analytics,
            get_bridge_crosschain_flows,
            get_protocol_health_score,
            detect_tvl_dump_risk,
            get_alpha_opportunities,
        ]
        return base_tools + self.handoff_tools

    def get_middleware(self) -> list:
        return get_base_middleware()

    def get_agent(self, agent_config: AgentConfig, **kwargs):
        self._prepare_handoff_tools(
            handoff_instructions=kwargs.get("handoff_instructions", {})
        )

        llm = self._construct_llm_model(agent_config)
        with open("/Users/barrytran/Documents/zoan/zoan-llm-backend/prompt_draft/a.txt", "r") as f:
            system_prompt = f.read()

        return create_agent(
            model=llm,
            tools=list(self.get_toolset()),
            system_prompt=system_prompt,
            middleware=self.get_middleware(),
            name=self.SANITIZED_NAME,
            checkpointer=kwargs.get("checkpointer"),
            store=kwargs.get("store"),
        )


defi_llama_agent = DefiLlamaAgent()
