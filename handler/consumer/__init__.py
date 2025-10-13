from typing import Dict
from handler.consumer.base import BaseMessageHandler
from handler.consumer.completion import (
    consumer_topic as completion_consumer_topic,
    completion_message_handler,
)
from handler.consumer.minio_bucket import (
    consumer_topic as minio_consumer_topic,
    minio_bucket_handler,
)
from config.logging import get_logger
from utils.enums import *

logger = get_logger()

class MessageConsumer:
    """Scalable message consumer that handles multiple topics"""
    
    def __init__(self):
        self._handlers: Dict[str, BaseMessageHandler] = {}
        self._topic_patterns: Dict[str, BaseMessageHandler] = {}
    
    def register_handler(self, topic: str, handler: BaseMessageHandler) -> None:
        """Register a handler for a specific topic"""
        self._handlers[topic] = handler
    
    def register_pattern_handler(self, pattern: str, handler: BaseMessageHandler) -> None:
        """Register a handler for a topic pattern (for future pattern matching)"""
        self._topic_patterns[pattern] = handler
    
    def get_handler(self, topic: str) -> BaseMessageHandler:
        """Get handler for a topic"""
        # First check exact match
        if topic in self._handlers:
            return self._handlers[topic]
        
        # Check pattern matches (could be extended with regex)
        for pattern, handler in self._topic_patterns.items():
            if pattern in topic:  # Simple substring match, can be enhanced
                return handler
        
        return None
    
    async def on_message(self, key: str, value: str, headers: Dict, meta: Dict) -> bool:
        """Main message processing method"""
        topic = meta.get("topic")
        if not topic:
            logger.error("No topic found in message metadata")
            return False
        
        handler = self.get_handler(topic)
        if not handler:
            logger.error("No handler found for topic: %s", topic)
            return False
        
        try:
            return await handler.handle(key, value, headers, meta)
        except Exception as e:
            logger.error("Error processing message for topic %s: %s", topic, str(e))
            return False

# Global consumer instance
message_consumer = MessageConsumer()

# Register handlers
message_consumer.register_handler(completion_consumer_topic, completion_message_handler)
message_consumer.register_handler(minio_consumer_topic, minio_bucket_handler)