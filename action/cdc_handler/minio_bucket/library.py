"""
Library processor for handling MinIO bucket notifications and updating Qdrant vector database.

This module provides processors for different types of media and files:
- MediaProcessor: Handles images and videos (with future video support)
- FileProcessor: Handles text-based files (PDF, DOC, TXT, etc.)
- Processor: Main processor that orchestrates the above processors

The processor supports:
- Image files: JPEG, PNG, GIF, BMP, WebP
- Text files: PDF, TXT, DOC, DOCX
- Future video support: Ready for extension

Features:
- Dual embedding approach for images (visual + text description)
- Proper error handling and logging
- Resource cleanup for MinIO connections
- Unified processing architecture
"""
import uuid
from typing import Optional, List, Type

from qdrant_client.http import models as qm
from action.cdc_handler.base import BaseProcessor

from internal.vectorizer import MediaProcessor, FileProcessor
from services.qdrant_library_client import qdrant_library_client
from services.minio_library_client import minio_library_client
from model.minio_bucket import BucketNotification

from config.logging import get_logger
from utils.enums import *

logger = get_logger()
    
class Processor(BaseProcessor):
    """
    Modern library processor that handles both media and file notifications.
    Uses the newer MediaProcessor and FileProcessor for better organization.
    """
    
    def __init__(self):
        self.qdrant_client = qdrant_library_client
        self.minio_client = minio_library_client
        
    def _is_supported_file_type(self, mimetype: str) -> bool:
        """Check if the file type is supported by any processor."""
        return (MediaProcessor.is_allowed_mime_type(mimetype) or 
                FileProcessor.is_allowed_mime_type(mimetype))
    
    def _upsert_points(self, points: List[qm.PointStruct]) -> None:
        """Upsert points to Qdrant database."""
        try:
            self.qdrant_client.client.upsert(
                collection_name=self.qdrant_client.collection_name,
                points=points
            )
            logger.debug(f"Successfully upserted {len(points)} points to Qdrant")
        except Exception as e:
            logger.error(f"Failed to upsert points to Qdrant: {e}")
            raise
    
    def _delete_by_object_key(self, object_key: str) -> None:
        """Delete points from Qdrant by object key."""
        try:
            self.qdrant_client.client.delete(
                collection_name=self.qdrant_client.collection_name,
                points_selector=qm.Filter(
                    must=[qm.FieldCondition(
                        key="object_key",
                        match=qm.MatchValue(value=object_key)
                    )]
                )
            )
            logger.debug(f"Successfully deleted points for object key: {object_key}")
        except Exception as e:
            logger.error(f"Failed to delete points for object key {object_key}: {e}")
            raise
    
    def _convert_points(self, bucket_name: str, object_key: str, mimetype: str, owner: str) -> List[qm.PointStruct]:
        """Convert bucket notification to Qdrant points using appropriate processor."""
        self._delete_by_object_key(object_key)
        if mimetype in MediaProcessor.ALLOWED_MIME_TYPES:
            return MediaProcessor.handle(bucket_name, object_key, mimetype, owner)
        elif mimetype in FileProcessor.ALLOWED_MIME_TYPES:
            return FileProcessor.handle(bucket_name, object_key, mimetype, owner)
        
        # Future video support can be added here
        
    def _handle_object_created(self, bucket_name: str, object_key: str, mimetype: str, owner: str) -> None:
        """Handle object creation events using appropriate processor."""
            
        try:
            points = self._convert_points(bucket_name, object_key, mimetype, owner)
            if len(points) > 0:
                self._upsert_points(points)
                logger.debug(f"Successfully processed creation of {object_key} ({mimetype})")
            else:
                logger.warning(f"No points generated for {object_key}")
                
            logger.info(f"[LibraryProcessor] Processed creation for {object_key}")
        except Exception as e:
            logger.error(f"Failed to handle object creation for {object_key}: {e}")
        
    def _handle_object_removed(self, object_key: str) -> None:
        """Handle object removal events."""
        try:
            self._delete_by_object_key(object_key)
            logger.info(f"[LibraryProcessor] Processed deletion for {object_key}")
        except Exception as e:
            logger.error(f"Failed to handle object removal for {object_key}: {e}")
        
    async def process_notification(self, bucket_notification: BucketNotification) -> None:
        """Process MinIO bucket notification and update Qdrant collection.""" 
        bucket_name = bucket_notification.get_bucket_name()
        object_key = bucket_notification.key.replace(f"{bucket_name}/", "", 1)
        owner = bucket_notification.get_owner()
        
        try:
            if bucket_notification.is_created_event():
                mimetype = bucket_notification.get_mimetype()
        
                if not self._is_supported_file_type(mimetype):
                    logger.debug(f"Unsupported file type '{mimetype}' for object: {object_key}")
                    return
                
                self._handle_object_created(bucket_name, object_key, mimetype, owner)
            elif bucket_notification.is_removed_event():
                self._handle_object_removed(object_key)
            else:
                logger.debug(f"[LibraryProcessor] Unhandled event type: {bucket_notification.event_name}")
                
        except Exception as e:
            logger.error(f"[LibraryProcessor] Failed to process notification: {e}")
            raise