from config import Config
from qdrant_client.http import models as qm
from external.qdrant.client import QdrantConfig, Client

DEFAULT_COLLECTION_VECTORS_CONFIG = {
    "image": qm.VectorParams(size=512, distance=qm.Distance.COSINE),
    "text":  qm.VectorParams(size=1536, distance=qm.Distance.COSINE),
}
DEFAULT_INDEX_CONFIG = {
    "owner": "keyword",
    "mimetype": "keyword",
    "url": "keyword",
}

class Service:
    """Qdrant client for library collection"""
    def __init__(self):
        self.collection_name = Config.QDRANT_LIBRARY_COLLECTION_NAME
        config = QdrantConfig(
            collection_name=self.collection_name,
            vectors_config=DEFAULT_COLLECTION_VECTORS_CONFIG,
            index_config=DEFAULT_INDEX_CONFIG,
        )
        self.client = Client(config).client
    
    def get_point_id_by_object_key(self, object_key: str) -> list[str]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            limit=1,
            query_filter=qm.Filter(
                must=[qm.FieldCondition(
                    key="object_key",
                    match=qm.MatchValue(value=object_key)
                )]
            )
        )
        
        return [str(point.id) for point in response.points] 
        
service = Service()