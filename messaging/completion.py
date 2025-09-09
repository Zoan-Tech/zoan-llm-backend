import json
from action import completion_action

from config.logging import get_logger

from model.completion import CompletionRequest

logger = get_logger()

TOPIC_CREATE_COMPLETION = "llm.channel.completion"

async def completion_message_handler(key, value, headers, meta):
    value = json.loads(value)
    completion_object = CompletionRequest(**value)
    logger.info("Received completion request: %s", completion_object.model_dump())
    await completion_action.create_completion(
        user_id=completion_object.user_id,
        conversation_id=completion_object.conversation_id,
        message=completion_object.message,
        agents=completion_object.agents,
        use_conversation_cache=completion_object.use_conversation_cache
    )
    return True

TOPIC_HANDLER_MAP = {
    TOPIC_CREATE_COMPLETION: completion_message_handler,
}

async def on_message(key, value, headers, meta):
    topic = meta["topic"]
    handler = TOPIC_HANDLER_MAP.get(topic)
    if not handler:
        logger.error("no handler for topic: %s", topic)
        return True
    return await handler(key, value, headers, meta)

