"""Agent Reply Worker for processing agent mention events."""

import asyncio
import json
import traceback
from typing import Optional

from config.logging import get_logger
from action.worker.base import BaseWorker
from internal.database import SessionLocal
from internal.database.kafka_events import KafkaEventRepository
from model.kafka.agent_mention import AgentMentionEvent
from action.completion.swarm import swarm_completion
from handler.kafka.producer.agent_reply import agent_reply_producer

logger = get_logger()


class AgentReplyWorker(BaseWorker):
    """
    Worker that processes agent mention events from the database.
    
    This worker:
    1. Polls for pending agent mention events from the database
    2. Invokes swarm_completion.create_agent_completion for each event
    3. Sends the agent's reply back to Kafka via agent_reply_producer
    4. Updates event status (completed/failed)
    5. Handles retries and dead letter queue
    6. Resets stuck events that timeout
    """
    
    def __init__(
        self,
        poll_interval: float = 1.0,
        batch_size: int = 10,
        processing_timeout: int = 300,
        asyncio_loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        Initialize the Agent Reply worker.
        
        Args:
            poll_interval: Seconds to wait between polling cycles
            batch_size: Maximum number of events to process per batch
            processing_timeout: Timeout in seconds for stuck events
            asyncio_loop: Event loop for async operations
        """
        super().__init__(
            name="AgentReplyWorker",
            poll_interval=poll_interval,
            asyncio_loop=asyncio_loop,
        )
        
        self.batch_size = batch_size
        self.processing_timeout = processing_timeout
        
    async def process(self):
        """Process a batch of pending agent mention events."""
        db = SessionLocal()
        
        try:
            # Fetch pending events
            events = KafkaEventRepository.get_pending_events(
                db=db,
                limit=self.batch_size
            )
            
            if not events:
                # No events to process, also check for stuck events
                await self._reset_stuck_events()
                return
            
            logger.debug(f"Processing batch of {len(events)} agent mention events")
            
            # Process each event
            for event in events:
                try:
                    # Mark as processing
                    KafkaEventRepository.mark_processing(db, event.id)
                    
                    # Parse message value
                    try:
                        message_data = json.loads(event.message_value)
                        agent_mention_event = AgentMentionEvent(**message_data)
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        error_msg = f"Invalid event data: {str(e)}"
                        logger.error(error_msg)
                        KafkaEventRepository.mark_failed(
                            db=db,
                            event_id=event.id,
                            error_message=error_msg,
                        )
                        continue
                    
                    # Create agent config (TODO: fetch from database based on agent_id)
                    # For now, using a placeholder - this should be replaced with actual agent config fetching
                    agent_configs = agent_mention_event.agent_configs
                    logger.debug(agent_mention_event.dict())
                    for agent_config in agent_configs:
                        # Invoke agent completion
                        reply_content = await swarm_completion.create_agent_completion(
                            user_id=agent_mention_event.user_id,
                            user_wallet_id=agent_mention_event.user_wallet_id,
                            user_wallet_address=agent_mention_event.user_wallet_address,
                            conversation_id=agent_mention_event.post_id,  # Use post_id as conversation_id
                            message=agent_mention_event.content,
                            agent_config=agent_config,
                            attachments=agent_mention_event.metadata.attachments,
                            metadata={
                                "agent_mention_event": agent_mention_event
                            }
                        )
                        
                        logger.debug(f"Agent completion result: {reply_content}")
                        
                        # Send reply to Kafka
                        agent_reply_producer.send_reply(
                            event_id=f"{agent_mention_event.id}-{agent_config.id}",
                            post_id=agent_mention_event.post_id,
                            agent_id=agent_config.id,
                            reply_content=reply_content,
                            comment_id=agent_mention_event.comment_id,
                            metadata=agent_mention_event.metadata,
                        )
                    
                    # Mark as completed
                    KafkaEventRepository.mark_completed(db, event.id)
                    logger.info(
                        f"Successfully processed event {event.id} "
                        f"(event_id={agent_mention_event.id})"
                    )
                
                except Exception as e:
                    logger.exception(f"Failed to process event {event.id}: {str(e)}")
                    
                    # Mark as failed with retry logic
                    KafkaEventRepository.mark_failed(
                        db=db,
                        event_id=event.id,
                        error_message=str(e),
                        error_traceback=traceback.format_exc(),
                    )
        
        except Exception as e:
            logger.exception(f"Error in process batch: {e}")
        
        finally:
            db.close()
    
    async def _reset_stuck_events(self):
        """Reset events that have been stuck in PROCESSING state."""
        db = SessionLocal()
        
        try:
            stuck_events = KafkaEventRepository.get_stuck_events(
                db=db,
                timeout_seconds=self.processing_timeout,
            )
            
            if stuck_events:
                logger.warning(f"Found {len(stuck_events)} stuck events, resetting them")
                
                for event in stuck_events:
                    KafkaEventRepository.reset_stuck_event(db, event.id)
                    logger.info(f"Reset stuck event {event.id}")
        
        except Exception as e:
            logger.exception(f"Error resetting stuck events: {e}")
        
        finally:
            db.close()
