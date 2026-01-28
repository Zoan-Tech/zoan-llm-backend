"""Agent Reply Kafka Producer Handler."""

from typing import Optional, Dict, Any

from config.logging import get_logger
from config import Config
from handler.kafka.producer import BaseProducer
from model.kafka.agent_reply import AgentReplyEvent

logger = get_logger()


class AgentReplyProducer(BaseProducer):
    """
    Producer for agent reply events.
    
    Publishes agent responses to the KAFKA_AGENT_REPLY_TOPIC topic.
    """
    
    def __init__(self):
        """Initialize the agent reply producer."""
        super().__init__()
        self.topic = Config.KAFKA_AGENT_REPLY_TOPIC
    
    def send_reply(
        self,
        event_id: str,
        post_id: str,
        agent_id: str,
        reply_content: list,
        comment_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None, # Use to handle attachments etc.
    ):
        """
        Send an agent reply message to Kafka.
        
        Args:
            event_id: Original event ID that triggered the reply
            post_id: Post ID where the reply should be posted
            agent_id: Agent ID that generated the reply
            reply_content: The actual reply content
            user_id: User ID who triggered the mention
            comment_id: Optional comment ID if replying to a comment
            metadata: Additional metadata
        """
        message = AgentReplyEvent(
            content=reply_content,
            post_id=post_id,
            parent_comment_id=comment_id,
            agent_id=agent_id,
        )
        
        self.send(
            topic=self.topic,
            value=message.model_dump(exclude_none=True),
            key=event_id,  # Use event_id as key for partitioning
            serialize_json=True,
        )

# Global instance
agent_reply_producer = AgentReplyProducer()
