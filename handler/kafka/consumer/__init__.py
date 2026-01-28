"""Base Kafka Consumer for handler layer."""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable

from config.logging import get_logger
from external.kafka.service import KafkaConsumer as ServiceKafkaConsumer
from config import Config

logger = get_logger()


class BaseConsumer(ABC):
    """
    Base Kafka Consumer class for the handler layer.
    
    Subclasses must implement:
    - topic: class attribute defining the topic to consume
    - handle_message: async method to process messages
    """
    
    topic: str = None  # Must be set by subclasses
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        group_id: str = None,
        enable_auto_commit: bool = False,
        auto_offset_reset: str = "earliest",
        extra_consumer_conf: Optional[Dict[str, Any]] = None,
        asyncio_loop: asyncio.AbstractEventLoop = None,
    ):
        """
        Initialize the base consumer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (defaults to Config.KAFKA_BROKERS)
            group_id: Consumer group ID (defaults to Config.KAFKA_GROUP_ID)
            enable_auto_commit: Whether to enable auto commit
            auto_offset_reset: Auto offset reset strategy
            extra_consumer_conf: Additional consumer configuration
            asyncio_loop: Asyncio event loop for async message handlers
        """
        if not self.topic:
            raise ValueError(f"{self.__class__.__name__} must define a 'topic' class attribute")
        
        self.bootstrap_servers = bootstrap_servers or Config.KAFKA_BROKERS
        self.group_id = group_id or Config.KAFKA_GROUP_ID
        self.asyncio_loop = asyncio_loop
        
        self.consumer = ServiceKafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            consumer_topics=[self.topic],
            enable_auto_commit=enable_auto_commit,
            auto_offset_reset=auto_offset_reset,
            enable_auto_offset_store=False,
            extra_consumer_conf=extra_consumer_conf,
            asyncio_loop=asyncio_loop,
        )
    
    @abstractmethod
    async def handle_message(
        self,
        key: str,
        value: bytes,
        headers: Dict[str, str],
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Handle a consumed message. Must be implemented by subclasses.
        
        Args:
            key: Message key
            value: Raw message value (bytes)
            headers: Message headers
            metadata: Message metadata (topic, partition, offset, timestamp)
        
        Returns:
            True to commit the message, False to skip
        """
        pass
    
    def _parse_json_value(self, value: bytes) -> Dict[str, Any]:
        """
        Parse JSON value from bytes.
        
        Args:
            value: Raw message value
        
        Returns:
            Parsed JSON dictionary
        
        Raises:
            json.JSONDecodeError: If value is not valid JSON
        """
        try:
            return json.loads(value.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {str(e)}")
            raise
    
    async def _on_message(
        self,
        key: str,
        value: bytes,
        headers: Dict[str, str],
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Internal message handler wrapper.
        
        Args:
            key: Message key
            value: Raw message value
            headers: Message headers
            metadata: Message metadata
        
        Returns:
            True to commit the message, False to skip
        """
        try:
            logger.debug(
                f"Received message on topic '{metadata.get('topic')}' "
                f"[partition={metadata.get('partition')}, offset={metadata.get('offset')}]"
            )
            
            should_commit = await self.handle_message(key, value, headers, metadata)
            
            if should_commit:
                logger.debug(f"Successfully processed message at offset {metadata.get('offset')}")
            else:
                logger.warning(f"Message processing returned False, skipping commit")
            
            return should_commit
            
        except Exception as e:
            logger.exception(
                f"Error handling message on topic '{metadata.get('topic')}' "
                f"at offset {metadata.get('offset')}: {str(e)}"
            )
            # Return False to not commit on error
            return False
    
    def start(self, poll_timeout: float = 1.0):
        """
        Start consuming messages.
        
        Args:
            poll_timeout: Poll timeout in seconds
        """
        self.consumer.start_consumer(
            on_message=self._on_message,
            poll_timeout=poll_timeout,
        )
    
    def stop(self):
        """Stop consuming messages."""
        logger.info(f"Stopping consumer for topic '{self.topic}'")
        self.consumer.stop_consumer()
    
    def close(self):
        """Close the consumer."""
        logger.info(f"Closing consumer for topic '{self.topic}'")
        self.consumer.close()
