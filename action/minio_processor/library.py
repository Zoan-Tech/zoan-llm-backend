import os
import uuid
from PIL import Image
from typing import Optional, List
import numpy as np
from sentence_transformers import SentenceTransformer

from qdrant_client.http import models as qm
from action.minio_processor.base import BaseProcessor
from services.qdrant_service import QdrantService, QdrantConfig
from services.minio_service import MinioService, MinioConfig
from model.minio_bucket import BucketNotification, QdrantPayload

from config import Config
from config.logging import get_logger
from utils.enums import *

logger = get_logger()

DEFAULT_COLLECTION_VECTORS_CONFIG = {
    "image": qm.VectorParams(size=512, distance=qm.Distance.COSINE),
    "text":  qm.VectorParams(size=512, distance=qm.Distance.COSINE),
}
DEFAULT_INDEX_CONFIG = {
    "owner": "keyword",
    "mimetype": "keyword",
    "url": "keyword",
}
class Processor(BaseProcessor):
    def __init__(self, qdrant_config: Optional[QdrantConfig] = None, minio_config: Optional[MinioConfig] = None):
        if qdrant_config is None:
            qdrant_config = QdrantConfig(
                collection_name=Config.QDRANT_LIBRARY_COLLECTION_NAME,
                vectors_config=DEFAULT_COLLECTION_VECTORS_CONFIG,
                index_config=DEFAULT_INDEX_CONFIG,
            )
        if minio_config is None:
            minio_config = MinioConfig(bucket="library")
        self.qdrant_client = QdrantService(qdrant_config).client
        self.minio_client = MinioService(minio_config).client
        self.collection_name = qdrant_config.collection_name
        self.model = SentenceTransformer("clip-ViT-B-32")  # 512-d embeddings
        
    def _load_image_from_minio(self, bucket: str, object_key: str) -> Optional[Image.Image]:
        try:
            response = self.minio_client.get_object(bucket, object_key)
            img = Image.open(response).convert("RGB")
            response.close()
            response.release_conn()
            return img
        except Exception as e:
            logger.error(f"Failed to load image from MinIO: {e}")
            return None
        
    def _construct_vector_from_text(self, text: str) -> np.ndarray:
        vec: np.ndarray = self.model.encode([text], batch_size=1, convert_to_numpy=True, normalize_embeddings=True)[0]
        return vec
    
    def get_point_id_by_object_key(self, object_key: str):
        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            limit=1,
            query_filter=qm.Filter(
                must=[qm.FieldCondition(
                    key="object_key",
                    match=qm.MatchValue(value=object_key)
                )]
            )
        )
        if len(response.points) > 0:
            return response[0].id
        return None
        
    def upsert_image(self, img: Image.Image, payload: QdrantPayload) -> None:
        point_id = self.get_point_id_by_object_key(payload.object_key)
        point_id = point_id or str(uuid.uuid4())
            
        vec: np.ndarray = self.model.encode([img], batch_size=1, convert_to_numpy=True, normalize_embeddings=True)[0]
        self.qdrant_client.upsert(
            self.collection_name,
            points=[qm.PointStruct(
                id=point_id,
                vector={
                    "image": vec.tolist(),
                },
                payload=payload.model_dump()
            )]
        )
    
    def delete_by_object_key(self, object_key: str) -> None:
        self.qdrant_client.delete(
            collection_name=self.collection_name,
            points_selector=qm.Filter(
                must=[qm.FieldCondition(
                    key="object_key",
                    match=qm.MatchValue(value=object_key)
                )]
            )
        )
        
    def _handle_object_created(self, bucket_notification: BucketNotification) -> None:
        bucket_name = bucket_notification.get_bucket_name()
        object_key = bucket_notification.key.replace(f"{bucket_name}/", "", 1)
        img = self._load_image_from_minio(bucket_name, object_key)
        
        if img is None:
            logger.error(f"Image at {object_key} could not be loaded.")
            return
        
        payload = QdrantPayload(
            bucket=bucket_name,
            object_key=object_key,
            owner=bucket_notification.get_owner(),
            mimetype=bucket_notification.get_mimetype(),
        )
        self.upsert_image(img, payload)
        
    def _handle_object_removed(self, bucket_notification: BucketNotification) -> None:
        object_key = bucket_notification.get_object_key()
        self.delete_by_object_key(object_key)
        
    async def process_notification(self, bucket_notification: BucketNotification) -> None:
        """Process MinIO bucket notification and update Qdrant collection"""
        if bucket_notification.is_created_event():
            logger.debug(f"[LibraryProcessor] Handling object created event for {bucket_notification.key}")
            self._handle_object_created(bucket_notification)
        elif bucket_notification.is_removed_event():
            logger.debug(f"[LibraryProcessor] Handling object removed event for {bucket_notification.key}")
            self._handle_object_removed(bucket_notification)
        else:
            logger.debug(f"[LibraryProcessor] Unhandled event type: {bucket_notification.event_name}")