"""
Completion action module.

This module provides completion actions using LangGraph and different streaming patterns:
- KafkaCompletionAction: Sends chunks via Kafka topic
- GrpcCompletionAction: Yields chunks directly as AsyncGenerator

For backward compatibility, the default `completion_action` instance uses Kafka.
"""

from action.completion.base import BaseCompletionAction
from action.completion.kafka import KafkaCompletionAction, kafka_completion_action
from action.completion.grpc import GrpcCompletionAction, grpc_completion_action

# Export all classes and instances
__all__ = [
    'BaseCompletionAction',
    'KafkaCompletionAction', 
    'GrpcCompletionAction',
    'kafka_completion_action',
    'grpc_completion_action',
    'completion_action',  # Backward compatibility
]