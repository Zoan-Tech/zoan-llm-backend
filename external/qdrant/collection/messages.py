from typing import List, Optional
from config import Config
from qdrant_client.http import models as qm
from external.qdrant.client import QdrantConfig, Client
from config.logging import get_logger
from utils.const.multimodal import VECTOR_DIMENSION

logger = get_logger()

# Qdrant collection field names
FIELD_USER_ID = "user_id"
FIELD_CONVERSATION_ID = "conversation_id"
FIELD_ATTACHMENT_URL = "attachment_url"
FIELD_TEXT = "text"
FIELD_CHUNK_INDEX = "chunk_index"
VECTOR_NAME_TEXT = "text"

DEFAULT_MESSAGES_VECTORS_CONFIG = {
    VECTOR_NAME_TEXT: qm.VectorParams(size=VECTOR_DIMENSION, distance=qm.Distance.COSINE),
}

DEFAULT_MESSAGES_INDEX_CONFIG = {
    FIELD_USER_ID: "keyword",
    FIELD_CONVERSATION_ID: "keyword",
    FIELD_ATTACHMENT_URL: "keyword",
}

class Service:
    """Qdrant client for messages collection - stores chunked document content"""
    def __init__(self):
        self.collection_name = Config.QDRANT_MESSAGES_COLLECTION_NAME
        config = QdrantConfig(
            collection_name=self.collection_name,
            vectors_config=DEFAULT_MESSAGES_VECTORS_CONFIG,
            index_config=DEFAULT_MESSAGES_INDEX_CONFIG,
        )
        self.client = Client(config).client
    
    def store_document_chunks(
        self,
        user_id: str,
        conversation_id: str,
        attachment_url: str,
        chunks: List[dict],
    ) -> bool:
        """
        Store document chunks in the messages collection.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            attachment_url: Original attachment URL
            chunks: List of dicts with 'text' and 'vector' keys
            
        Returns:
            True if successful, False otherwise
        """
        try:
            points = []
            for idx, chunk in enumerate(chunks):
                point_id = f"{user_id}_{conversation_id}_{attachment_url}_{idx}"
                points.append(
                    qm.PointStruct(
                        id=point_id,
                        vector={VECTOR_NAME_TEXT: chunk["vector"]},
                        payload={
                            FIELD_USER_ID: user_id,
                            FIELD_CONVERSATION_ID: conversation_id,
                            FIELD_ATTACHMENT_URL: attachment_url,
                            FIELD_TEXT: chunk["text"],
                            FIELD_CHUNK_INDEX: idx,
                        }
                    )
                )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Stored {len(chunks)} chunks for attachment {attachment_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to store document chunks: {e}")
            return False
    
    def search_relevant_chunks(
        self,
        query_vector: List[float],
        user_id: str,
        conversation_id: str,
        limit: int = None,
        score_threshold: float = None,
        filter: Optional[dict] = None,
    ) -> List[dict]:
        """
        Search for relevant document chunks based on query.
        
        Args:
            query_vector: Embedding vector of the query
            user_id: User ID to filter by
            conversation_id: Conversation ID to filter by
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter: Optional filter to narrow down search results (e.g., {'attachment_url': 'specific_file.pdf'})
            
        Returns:
            List of relevant chunks with text and metadata
        """
        try:
            from utils.const.multimodal import DEFAULT_SEARCH_LIMIT, DEFAULT_SCORE_THRESHOLD
            
            # Use defaults if not provided
            if limit is None:
                limit = DEFAULT_SEARCH_LIMIT
            if score_threshold is None:
                score_threshold = DEFAULT_SCORE_THRESHOLD
            
            # Build base filter
            must_conditions = [
                qm.FieldCondition(
                    key=FIELD_USER_ID,
                    match=qm.MatchValue(value=user_id)
                ),
                qm.FieldCondition(
                    key=FIELD_CONVERSATION_ID,
                    match=qm.MatchValue(value=conversation_id)
                )
            ]
            
            # Add optional filter conditions
            should_conditions = []
            if filter:
                for key, value in filter.items():
                    if key == 'object_key':
                        should_conditions.append(
                            qm.FieldCondition(
                                key=key,
                                match=qm.MatchTextAny(text_any=value)
                            )
                        )
                    elif key == 'mimetype':
                        should_conditions.append(
                            qm.FieldCondition(
                                key=key,
                                match=qm.MatchText(text=value)
                            )
                        )
            
            query_filter = qm.Filter(must=must_conditions)
            if should_conditions:
                query_filter.should = should_conditions
            
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=VECTOR_NAME_TEXT,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
            
            chunks = []
            for point in results.points:
                chunks.append({
                    "text": point.payload.get(FIELD_TEXT, ""),
                    "attachment_url": point.payload.get(FIELD_ATTACHMENT_URL, ""),
                    "chunk_index": point.payload.get(FIELD_CHUNK_INDEX, 0),
                    "score": point.score,
                })
            
            logger.info(f"Found {len(chunks)} relevant chunks for query")
            return chunks
        except Exception as e:
            logger.error(f"Failed to search document chunks: {e}")
            return []
    
    def delete_conversation_documents(
        self,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        """
        Delete all document chunks for a conversation.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(
                        must=[
                            qm.FieldCondition(
                                key=FIELD_USER_ID,
                                match=qm.MatchValue(value=user_id)
                            ),
                            qm.FieldCondition(
                                key=FIELD_CONVERSATION_ID,
                                match=qm.MatchValue(value=conversation_id)
                            )
                        ]
                    )
                )
            )
            logger.info(f"Deleted documents for conversation {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation documents: {e}")
            return False

service = Service()
