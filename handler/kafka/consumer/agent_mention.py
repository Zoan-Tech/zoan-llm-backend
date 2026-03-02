"""Agent Mention Kafka Consumer Handler."""

import json
from typing import Dict, Any

from config.logging import get_logger
from config import Config
from handler.kafka.consumer import BaseConsumer
from internal.database import SessionLocal
from internal.database.kafka_events import KafkaEventRepository, EventStatus

logger = get_logger()


class AgentMentionConsumer(BaseConsumer):
    """
    Consumer for agent mention events.
    
    Handles messages from the KAFKA_AGENT_MENTION_TOPIC topic.
    This consumer is triggered when an agent is mentioned in a conversation.
    """
    
    topic = Config.KAFKA_AGENT_MENTION_TOPIC
    
    async def handle_message(
        self,
        key: str,
        value: bytes,
        headers: Dict[str, str],
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Handle agent mention message by saving it to the database.
        
        Expected message format (JSON):
        {
            "id": "string",                    // Unique event ID
            "content": "string",              // Content that mentioned the agent
            "post_id": "string",              // ID of the post/comment
            "comment_id": "string",           // ID of the comment if comment mention (optional)
            "user_id": "string",              // User who created the content
            "agent_id": "string",             // Agent username mentioned
            "metadata": {}                     // Additional context (language, visibility, etc.)
        }
        
        Args:
            key: Message key (typically event_id or user_id)
            value: Raw message value (JSON bytes)
            headers: Message headers
            metadata: Message metadata (topic, partition, offset, timestamp)
        
        Returns:
            True to commit the message (after saving to DB), False to retry
        """
        db = SessionLocal()
        
        try:
            # Parse and validate JSON message
            try:
                message_data = self._parse_json_value(value)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON message, skipping: {str(e)}")
                return True  # Commit to avoid reprocessing invalid messages
            
            logger.info(
                f"Received agent mention event: "
                f"id={message_data.get('id')}, "
                f"user_id={message_data.get('user_id')}, "
                f"agent_id={message_data.get('agent_id')}, "
                f"post_id={message_data.get('post_id')}, "
                f"comment_id={message_data.get('comment_id')}"
            )
            
            # Save event to database for async processing
            KafkaEventRepository.create_event(
                db=db,
                topic=metadata.get("topic"),
                message_key=key,
                message_value=value.decode("utf-8"),
                partition=metadata.get("partition"),
                offset=metadata.get("offset"),
                headers=headers,
                consumer_name=self.__class__.__name__,
                max_retries=3,
            )
            return True  # Always commit Kafka message after saving to DB
            
        except Exception as e:
            logger.exception(
                f"Error saving agent mention message to database: {str(e)}"
            )
            db.rollback()
            # Return False to not commit - will retry the Kafka message
            return False
        
        finally:
            db.close()