"""
Completion action module.

This module provides completion actions using LangGraph and different streaming patterns:
- SwarmCompletion: Yields chunks directly as AsyncGenerator
"""

from action.completion.base import BaseCompletionAction
from action.completion.swarm import SwarmCompletion, swarm_completion

# Export all classes and instances
__all__ = [
    'BaseCompletionAction',
    'SwarmCompletion',
    'swarm_completion',
    'completion_action',  # Backward compatibility
]