from config import Config
from qdrant_client.http import models as qm
from services.connector.qdrant_service import QdrantService, QdrantConfig

DEFAULT_COLLECTION_VECTORS_CONFIG = {
    "image": qm.VectorParams(size=512, distance=qm.Distance.COSINE),
    "text":  qm.VectorParams(size=512, distance=qm.Distance.COSINE),
}
DEFAULT_INDEX_CONFIG = {
    "owner": "keyword",
    "mimetype": "keyword",
    "url": "keyword",
}

class QDrantLibraryClient:
    """Qdrant client for library collection"""
    def __init__(self):
        self.collection_name = Config.QDRANT_LIBRARY_COLLECTION_NAME
        config = QdrantConfig(
            collection_name=self.collection_name,
            vectors_config=DEFAULT_COLLECTION_VECTORS_CONFIG,
            index_config=DEFAULT_INDEX_CONFIG,
        )
        self.client = QdrantService(config).client
        
qdrant_library_client = QDrantLibraryClient()