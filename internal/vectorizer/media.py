from internal.vectorizer.base import *
import uuid
from PIL import Image
from typing import Optional, List, Any
import numpy as np
from io import BytesIO

from qdrant_client.http import models as qm

from internal.vectorizer.helper import media_info_generator
from services.minio_library_client import minio_library_client
from model.minio_bucket import QdrantPayload, MediaObject

from config.logging import get_logger
from utils.enums import *

logger = get_logger()

class MediaProcessor(BaseProcessor):
    """Processor for media files (images and videos)."""
    
    IMAGE_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp"]
    VIDEO_MIME_TYPES: List[str] = []  # Ready for future video processing
    
    ALLOWED_MIME_TYPES: List[str] = IMAGE_MIME_TYPES + VIDEO_MIME_TYPES
    
    @classmethod
    def _load_image(cls, bucket: str, object_key: str) -> Optional[MediaObject]:
        try:
            response = minio_library_client.client.get_object(bucket, object_key)
            image_name = object_key.split("/")[-1]
            image_data = response.read()
            
            # Create image from bytes
            image = Image.open(BytesIO(image_data)).convert("RGB")
            # Generate image content description using the same bytes
            image_content = media_info_generator.generate_media_info(image_name, image_data)
            
            response.close()
            response.release_conn()
            return MediaObject(
                media=image,
                media_content=[image_content],
                metadata={
                    "image_size": image.size,
                }
            )
        except Exception as e:
            logger.error(f"Failed to load image from MinIO: {e}")
            return None
        
    @classmethod
    def _load_video(cls, bucket: str, object_key: str) -> Optional[MediaObject]:
        """Load video from MinIO (placeholder for future implementation)."""
        # TODO: Implement video loading and frame extraction
        pass
        
    @classmethod
    def _load_media(cls, bucket: str, object_key: str, mimetype: str) -> Optional[MediaObject]:
        """Load media based on mimetype."""
        if mimetype in cls.IMAGE_MIME_TYPES:
            return cls._load_image(bucket, object_key)
        elif mimetype in cls.VIDEO_MIME_TYPES:
            return cls._load_video(bucket, object_key)
        else:
            logger.warning(f"Unsupported media type: {mimetype}")
            return None

        
    @classmethod
    def _construct_vector(cls, media: MediaObject, mimetype: str) -> List[dict[str, Any]]:
        """Construct vector embeddings for media objects."""
        if mimetype in cls.IMAGE_MIME_TYPES:
            try:
                # Generate image embedding
                image: np.ndarray = IMAGE_EMBEDDING_MODEL.encode([media.media], batch_size=1, convert_to_numpy=True, normalize_embeddings=True)[0]
                image_vec = image.tolist()
                
                return [{
                    "image": image_vec,
                    "text": TEXT_EMBEDDING_MODEL.embed_query(media_content),
                } for media_content in media.media_content]
            except Exception as e:
                logger.error(f"Failed to construct vector for {mimetype}: {e}")
                raise
        elif mimetype in cls.VIDEO_MIME_TYPES:
            ## Future video embedding construction can be added here
            return []