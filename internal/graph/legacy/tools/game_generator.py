from typing import Annotated
from langchain_core.tools import tool
from langchain_core.runnables.config import ensure_config

from config import Config
from services.qdrant_library_client import qm, qdrant_library_client
from internal.vectorizer.base import TEXT_EMBEDDING_MODEL

@tool
def search_library(
    query: Annotated[str, "The search query, related to game specifications, features, or themes"],
    offset: Annotated[int, "The offset for pagination, starting from 0, corresponds to the number of times the search has been performed."]
) -> str:
    """Search the library for relevant game specification/game feature or game themes/assets."""
    config = ensure_config()
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id", None)
    
    filter_ = qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=[user_id, "public"])
            )
        ]
    ) if user_id else qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=["public"])
            )
        ]
    )
    
    text_vector = TEXT_EMBEDDING_MODEL.embed_query(query)
        
    results = qdrant_library_client.client.search(
        collection_name=qdrant_library_client.collection_name,
        query_vector=("text", text_vector),
        query_filter=filter_,
        limit=5,
        offset=offset * 10,
    )
    
    search_result = f"Found {len(results)} results for query '{query}' with offset {offset}."
    search_item = "\n".join([
        (
         "-- {idx}. {object} - Score: {score:.4f} --\n"
         "  Content: {content}\n"
         "  URL: {url}\n"
         "  Metadata: {metadata}\n"
        ).format(
            idx=idx,
            object=object.payload.get("object_key", "N/A"),
            score=object.score,
            content=object.payload.get("content", "N/A"),
            url=f"{Config.MINIO_BROWSER_URL}/{object.payload.get('bucket', '')}/{object.payload.get('object_key', '')}",
            metadata=object.payload.get("metadata", {}),
        )
        for idx, object in enumerate(results)])
    
    return f"{search_result}\n{search_item}"