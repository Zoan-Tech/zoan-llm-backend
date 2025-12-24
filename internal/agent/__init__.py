"""
Built-in Internal Agents

This module contains specialized agents for various tasks:
- PrimaryAgent: Main supervisor agent
- GameGeneratorV1: Local HTML/CSS/JS game builder
- ContextAgent: Knowledge hub search specialist
"""
from internal.agent.base import BaseInternalAgent
from internal.agent.primary_agent import primary_agent
from internal.agent.game_generator import game_generator_v1

__all__ = [
    "primary_agent",
    "game_generator_v1",
    "BaseInternalAgent",
]
