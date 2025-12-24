"""
Completion action module.

This module provides completion actions using LangGraph and different streaming patterns:
- GrpcCompletionAction: Yields chunks directly as AsyncGenerator
"""

from action.completion.base import BaseCompletionAction
from action.completion.grpc import GrpcCompletionAction, grpc_completion_action

# Export all classes and instances
__all__ = [
    'BaseCompletionAction',
    'GrpcCompletionAction',
    'grpc_completion_action',
    'completion_action',  # Backward compatibility
]