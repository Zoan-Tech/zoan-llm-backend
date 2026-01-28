"""Kafka handler package."""

from .producer import BaseProducer
from .consumer import BaseConsumer

"""Kafka handler initialization and management."""

import asyncio
from typing import List, Dict, Type

from config.logging import get_logger
from handler.kafka.consumer.agent_mention import AgentMentionConsumer

logger = get_logger()


class KafkaHandlerManager:
    """
    Manager for dynamically loading and managing Kafka consumers.
    
    Automatically discovers and initializes consumer handlers from the
    handler/kafka/consumer directory.
    """
    
    def __init__(self, asyncio_loop: asyncio.AbstractEventLoop = None):
        """
        Initialize the Kafka handler manager.
        
        Args:
            asyncio_loop: Event loop for async message handlers
        """
        self.asyncio_loop = asyncio_loop
        self.consumers: List[BaseConsumer] = []
        self.consumer_classes: Dict[str, Type[BaseConsumer]] = {}
        self.topics: List[str] = []
    
    def initialize_consumers(self) -> List[BaseConsumer]:
        """
        Initialize all discovered consumer handlers.
        
        Returns:
            List of initialized consumer instances
        """
        self.consumer_classes = {
            "AgentMentionConsumer": AgentMentionConsumer
        }
        
        if not self.consumer_classes:
            logger.warning("No consumer classes discovered")
            return []
        
        consumers = []
        for consumer_name, consumer_class in self.consumer_classes.items():
            try:
                # Check if the consumer topic is configured
                if not consumer_class.topic:
                    logger.warning(
                        f"Consumer {consumer_name} has no topic configured, skipping"
                    )
                    continue
                
                # Initialize the consumer
                consumer = consumer_class(asyncio_loop=self.asyncio_loop)
                consumers.append(consumer)
                
            except Exception as e:
                logger.error(f"Failed to initialize consumer '{consumer_name}': {str(e)}", exc_info=True)
        
        self.consumers = consumers
        return consumers
    
    def start_all_consumers(self, poll_timeout: float = 1.0):
        """
        Start all initialized consumers.
        
        Args:
            poll_timeout: Poll timeout in seconds
        """
        if not self.consumers:
            logger.warning("No consumers to start")
            return
        
        for consumer in self.consumers:
            try:
                consumer.start(poll_timeout=poll_timeout)
                self.topics.append(consumer.topic)
            except Exception as e:
                logger.error(
                    f"Failed to start consumer for topic '{consumer.topic}': {str(e)}"
                )
                
    def stop_all_consumers(self):
        """Stop all running consumers."""
        if not self.consumers:
            return
        
        logger.info(f"Stopping {len(self.consumers)} Kafka consumers")
        
        for consumer in self.consumers:
            try:
                consumer.stop()
                logger.info(f"Stopped consumer for topic '{consumer.topic}'")
            except Exception as e:
                logger.error(
                    f"Failed to stop consumer for topic '{consumer.topic}': {str(e)}"
                )
    
    def close_all_consumers(self):
        """Close all consumers and cleanup resources."""
        if not self.consumers:
            return
        
        logger.info(f"Closing {len(self.consumers)} Kafka consumers")
        
        for consumer in self.consumers:
            try:
                consumer.close()
                logger.info(f"Closed consumer for topic '{consumer.topic}'")
            except Exception as e:
                logger.error(
                    f"Failed to close consumer for topic '{consumer.topic}': {str(e)}"
                )
        
        self.consumers = []

__all__ = ["BaseProducer", "BaseConsumer"]
