import os
import json
from typing import Dict
from action.completion import completion_action
from config.logging import get_logger
from model.completion import CompletionRequest
from handler.consumer.base import BaseMessageHandler
from utils.enums import *

logger = get_logger()

class CompletionMessageHandler(BaseMessageHandler):
    """Handler for completion messages"""
    
    async def handle(self, key: str, value: str, headers: Dict, meta: Dict) -> bool:
        try:
            parsed_value = json.loads(value)
            completion_object = CompletionRequest(**parsed_value)
            logger.debug("Received completion request: %s", completion_object.model_dump())
            
            await completion_action.create_completion(
                user_id=completion_object.user_id,
                conversation_id=completion_object.conversation_id,
                message=completion_object.message,
                agents=completion_object.agents,
                attachments=completion_object.attachments
            )
            return True
        except Exception as e:
            logger.error("Error handling completion message: %s", str(e))
            return False

DEFAULT_KAFKA_TOPIC_REQUEST = "llm.channel.completion"
consumer_topic = os.environ.get(SecretEnum.KAFKA_TOPIC_REQUEST.value, DEFAULT_KAFKA_TOPIC_REQUEST)