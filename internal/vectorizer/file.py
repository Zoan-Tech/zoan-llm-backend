from internal.vectorizer.base import *

from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from model.minio_bucket import MediaObject
from config import Config

from config.logging import get_logger

logger = get_logger()

EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

tokenizer: BaseTokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained(EMBED_MODEL_ID),
)
chunker = HybridChunker(tokenizer=tokenizer)

        
class FileProcessor(BaseProcessor):
    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "text/plain",
        "application/msword",
    ]
    converter = DocumentConverter()
    
    @classmethod
    def _load_media(cls, bucket: str, object_key: str, mimetype: str) -> Optional[MediaObject]:
        """Load file content from MinIO."""
        file_name = object_key.split("/")[-1]
        
        try:
            object_url = "{minio_url}/{bucket}/{object_key}".format(
                minio_url=Config.MINIO_BROWSER_URL,
                bucket=bucket,
                object_key=object_key
            )
            
            result = cls.converter.convert(
                object_url,
            )
            
            chunk_iter = chunker.chunk(dl_doc=result.document)

            chunks = list(chunk_iter)
            chunks = [chunk.text for chunk in chunks]
            
            return MediaObject(
                media=file_name,
                media_content=chunks,
                metadata={
                    "chunks": len(chunks),
                }
            )
        except Exception as e:
            logger.error(f"Failed to load file from MinIO: {e}")
            return None
        
        
    @classmethod
    def _construct_vector(cls, media: MediaObject, mimetype: str) -> List[dict[str, Any]]:
        """Construct vector embeddings for file content."""
        try:
            return [{
                "text": TEXT_EMBEDDING_MODEL.embed_query(media_content),
            } for media_content in media.media_content]
            
        except Exception as e:
            logger.error(f"Failed to construct vectors for file: {e}")
            return []