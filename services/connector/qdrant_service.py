import os
from typing import Optional
from qdrant_client import QdrantClient
from utils.enums import SecretEnum
from config import Config

class QdrantConfig:
    """Configuration for Qdrant service"""
    def __init__(
        self,
        collection_name: str,
        url: str = Config.QDRANT_URL,
        api_key: Optional[str] = Config.QDRANT_API_KEY,
        vectors_config: Optional[dict] = None,
        index_config: Optional[dict] = {},
    ):
        self.url = url
        self.collection_name = collection_name
        self.api_key = api_key
        self.vectors_config = vectors_config
        self.index_config = index_config

class QdrantService:
    """Qdrant service for vector storage and retrieval"""
    def __init__(self, config: QdrantConfig):
        self.client = QdrantClient(
            url=config.url,
            api_key=config.api_key,
        )
        self.collection_name = config.collection_name
        self._ensure_collection_exists(config.vectors_config, config.index_config)
        
    def _has_collection(self) -> bool:
        """Check if the collection exists in Qdrant"""
        collections = self.client.get_collections()
        if self.collection_name not in [c.name for c in collections.collections]:
            return False
        return True
    
    def _create_collection(self, vectors_config: dict = None, index_config: dict = {}):
        """Create the collection in Qdrant"""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=vectors_config,
        )
        if index_config:
            for field_name, field_schema in index_config.items():
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_schema
                )
        
    def _ensure_collection_exists(self, vectors_config: dict = None, index_config: dict = {}):
        """Ensure the collection exists in Qdrant"""
        try:
            if not self._has_collection():
                self._create_collection(vectors_config, index_config)
        except Exception as e:
            raise RuntimeError(f"Failed to ensure collection exists: {e}")