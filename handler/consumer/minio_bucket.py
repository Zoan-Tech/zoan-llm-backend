import os
import json
from typing import Dict, Callable
from handler.consumer.base import BaseMessageHandler
from model.minio_bucket import (
    BucketNotification,
)
from action.minio_processor.base import BaseProcessor
from action.minio_processor.library import Processor as LibraryProcessor

from config import Config
from config.logging import get_logger
from utils.enums import *

logger = get_logger()

class MinioBucketHandler(BaseMessageHandler):
    """Handler for MinIO bucket notifications"""
    def __init__(self, managed_buckets: Dict[str, BaseProcessor]):
        self._processor: Dict[str, BaseProcessor] = {}
        for bucket_name, processor in managed_buckets.items():
            self._register_processor(bucket_name, processor)
        
    def _register_processor(self, bucket_name: str, processor: BaseProcessor):
        self._processor[bucket_name] = processor
     
    async def handle(self, key: str, value: str, headers: Dict, meta: Dict) -> bool:
        try:
            parsed_value = json.loads(value)
            bucket_notification = BucketNotification(**parsed_value)
            logger.info("Received bucket notification: %s", bucket_notification.event_name)
            
            bucket_name = bucket_notification.get_bucket_name()
            await self._processor[bucket_name].process_notification(bucket_notification)
            return True
        except Exception as e:
            logger.error("Error handling bucket notification: %s", str(e))
            return False
        
managed_buckets = {
    "library": LibraryProcessor(),
}

minio_bucket_handler = MinioBucketHandler(managed_buckets)
consumer_topic = Config.KAFKA_TOPIC_MINIO_NOTIFY