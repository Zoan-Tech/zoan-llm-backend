"""
Built-in Internal Agents

This module contains specialized agents for various tasks:
- PrimaryAgent: Main supervisor agent
- GameGeneratorV1: Local HTML/CSS/JS game builder
- ContextAgent: Knowledge hub search specialist
- AsterPerpDexAgent: Perpetual futures trading on Aster DEX
- CoinGeckoAgent: Cryptocurrency market data and trends
"""
from internal.agent.base import BaseInternalAgent
from internal.agent.primary_agent import primary_agent
from internal.agent.game_generator import game_generator_v1
from internal.agent.aster_trading_agent import aster_trading_agent
from internal.agent.hyperliquid_trading_agent import hyperliquid_trading_agent
from internal.agent.coingecko_agent import coingecko_agent
from internal.agent.wallet_agent import wallet_agent
from internal.agent.defi_llama_agent import defi_llama_agent

__all__ = [
    "primary_agent",
    "game_generator_v1",
    "aster_trading_agent",
    "hyperliquid_trading_agent",
    "coingecko_agent",
    "wallet_agent",
    "defi_llama_agent",
    "BaseInternalAgent",
]
