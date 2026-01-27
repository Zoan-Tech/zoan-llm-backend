"""Base Kafka Producer for handler layer."""

from typing import Any, Optional, Dict

from config.logging import get_logger
from external.kafka.service import KafkaProducer as ServiceKafkaProducer
from config import Config

logger = get_logger()


class BaseProducer:
    """Base Kafka Producer class for the handler layer."""
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        extra_producer_conf: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the base producer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (defaults to Config.KAFKA_BROKERS)
            extra_producer_conf: Additional producer configuration
        """
        self.bootstrap_servers = bootstrap_servers or Config.KAFKA_BROKERS
        self.producer = ServiceKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            extra_producer_conf=extra_producer_conf,
        )
    
    def send(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        serialize_json: bool = True,
    ):
        """
        Send a message to a Kafka topic.
        
        Args:
            topic: Kafka topic name
            value: Message value (will be JSON serialized if serialize_json=True)
            key: Optional message key
            headers: Optional message headers
            serialize_json: Whether to serialize value as JSON
        """
        try:
            self.producer.produce(
                topic=topic,
                value=value,
                key=key,
                headers=headers,
                serialize_json=serialize_json,
            )
            logger.debug(f"Sent message to topic '{topic}' with key '{key}'")
        except Exception as e:
            logger.error(f"Failed to send message to topic '{topic}': {str(e)}")
            raise
    
    def flush(self, timeout: float = 10.0):
        """
        Flush producer buffer to ensure all messages are sent.
        
        Args:
            timeout: Maximum time to wait for flush in seconds
        
        Returns:
            Number of messages still in queue after flush
        """
        return self.producer.flush(timeout)
    
    def close(self):
        """Close the producer and flush remaining messages."""
        logger.info("Closing BaseProducer")
        self.producer.close()
