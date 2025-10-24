from typing import Optional, List, Any

from qdrant_client.http import models as qm

from utils.model import Model
from config.logging import get_logger
import uuid
from model.minio_bucket import QdrantPayload, MediaObject

logger = get_logger()

IMAGE_EMBEDDING_MODEL = Model.clip_ViT_B_32
TEXT_EMBEDDING_MODEL = Model.openai_text_embedding_3_small

class BaseProcessor:
    """Base class for processors."""
    ALLOWED_MIME_TYPES: List[str] = []
    
    @classmethod
    def is_allowed_mime_type(cls, mimetype: str) -> bool:
        return mimetype in cls.ALLOWED_MIME_TYPES
    
    @classmethod
    def _load_media(cls, bucket: str, object_key: str, mimetype: str) -> Optional[MediaObject]:
        """Load media based on mimetype. To be implemented by subclasses."""
        raise NotImplementedError
    
    @classmethod
    def _construct_vector(cls, media: MediaObject, mimetype: str) -> List[dict[str, Any]]:
        """Construct vector embeddings for media objects. To be implemented by subclasses."""
        raise NotImplementedError
    
    @classmethod
    def handle(cls,
        bucket_name: str,
        object_key: str,
        mimetype: str,
        owner: str = None,
    ) -> list[qm.PointStruct]:
        """Handle media processing and create Qdrant points."""
        points = []
        
        media = cls._load_media(bucket_name, object_key, mimetype)
        if media is None:
            logger.error(f"Media at {object_key} could not be loaded.")
            return points
        
        vectors = cls._construct_vector(media, mimetype)
        try:
            for idx, (content, vector) in enumerate(zip(media.media_content, vectors)):
                point_id = str(uuid.uuid4())
                payload = QdrantPayload(
                    bucket=bucket_name,
                    object_key=object_key,
                    mimetype=mimetype,
                    owner=owner,
                    media_name=media.media,
                    index=idx,
                    content=content,
                    metadata=media.metadata,
                )
                
                point = qm.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload.model_dump(),
                )
                points.append(point)
            
            return points
        except Exception as e:
            logger.error(f"Failed to construct point for media {object_key}: {e}")
            return points