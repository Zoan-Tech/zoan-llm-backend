import httpx

from io import BytesIO
from utils.model import Model
from PIL import Image
from model.vectorizer import (
    EmbedResponse,
)
from typing import Optional

IMAGE_EMBEDDING_MODEL = Model.clip_ViT_B_32
TEXT_EMBEDDING_MODEL = Model.openai_text_embedding_3_small

class Vectorizer:
    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        """Generate embeddings for a list of texts."""
        text_embedding = TEXT_EMBEDDING_MODEL.embed_query(text)
        return text_embedding
    
    @classmethod
    def embed_image(cls, image_url: str) -> list[float]:
        """Generate embeddings for a list of image URLs."""
        response = httpx.get(image_url, timeout=10.0)
        image_data = response.content
        
        # Create image from bytes
        image = Image.open(BytesIO(image_data)).convert("RGB")
        
        response.close()
        
        image_embedding = IMAGE_EMBEDDING_MODEL.encode(image)
        return image_embedding
    
    @classmethod
    def embed(cls, text: str, image_url: Optional[str]) -> EmbedResponse:
        """Generate embeddings for text and image."""
        text_embeddings = cls.embed_text(text)
        image_embeddings = cls.embed_image(image_url) if image_url else None
        
        return EmbedResponse(
            text=text_embeddings,
            image=image_embeddings
        )