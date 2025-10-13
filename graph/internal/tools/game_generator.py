from typing import Annotated
from langchain_core.tools import tool
from langchain_core.runnables.config import ensure_config

from config import Config
from services.qdrant_library_client import qm, qdrant_library_client
from utils.model import Model

@tool
def search_library(
    query: Annotated[str, "The search query, related to game specifications, features, or themes"],
    offset: Annotated[int, "The offset for pagination, starting from 0, corresponds to the number of times the search has been performed."]
) -> str:
    """Search the library for relevant game specification/game feature or game themes/assets."""
    config = ensure_config()
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id", None)
    
    text_vector = Model.clip_ViT_B_32.encode(query)
    
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
        
    results = qdrant_library_client.client.search(
        collection_name=qdrant_library_client.collection_name,
        query_vector=("image", text_vector),
        query_filter=filter_,
        limit=10,
        offset=offset * 10,
    )
    
    search_result = f"Found {len(results)} results for query '{query}' with offset {offset}."
    search_item = "\n".join([f"- Item {Config.MINIO_BROWSER_URL}/{object.payload['bucket']}/{object.payload['object_key']} with score {object.score}\n" for object in results])
    
    return f"{search_result}\n{search_item}"