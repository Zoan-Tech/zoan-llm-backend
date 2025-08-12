import os, json
from typing import Dict, Any
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from langgraph.graph.state import CompiledStateGraph
from psycopg import Connection
from langfuse import Langfuse

from model import AgentConfig
from graph.builder import GraphBuilder
from module.client import ModuleClient
from cache import GraphCache
from utils.enums import *

class CompletionAction:
    """Handles completion actions using LangGraph and a Postgres database."""

    def __init__(self, cache_ttl_seconds: int = None):
        """
        Initialize the CompletionAction with caching support.
        
        :param cache_ttl_seconds: TTL for cache entries. Defaults to 15 minutes if None.
        """
        self._setup_graph_memory()
        self._setup_graph_builder()
        # Initialize the graph cache
        self.graph_cache = GraphCache(ttl_seconds=cache_ttl_seconds)

    def _setup_graph_builder(self):
        """
        Setup the GraphBuilder with necessary clients and configurations.
        """
        module_client = ModuleClient()
        langfuse_client = Langfuse(
            host=os.environ.get(SecretEnum.LANGFUSE_HOST.value),
            public_key=os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value),
            secret_key=os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value),
        )
        self.graph_builder = GraphBuilder(
            module_client=module_client,
            langfuse_client=langfuse_client,
            checkpointer=self.saver,
            store=self.store,
        )

    def _setup_graph_memory(self):
        """
        Setup the memory for the graph builder.
        """
        conn_string = os.environ.get(SecretEnum.POSTGRES_CONN_STRING.value)
        conn = Connection.connect(conn_string, autocommit=True)

        # Checkpointer
        self.saver = PostgresSaver(conn)
        self.saver.setup()

        # Store
        self.store = PostgresStore(conn)
        self.store.setup()

    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: list[AgentConfig],
        use_conversation_cache: bool = True,
    ):
        """
        Create a completion using the specified model and messages.
        
        :param user_id: The user ID for the completion.
        :param conversation_id: The conversation ID for thread management.
        :param message: The user message to process.
        :param agents: List of agent configurations.
        :param use_conversation_cache: Whether to use conversation-based caching.
        :return: The response from the chat model.
        """
        compiled_graph = None
        
        # First, try to get cached graph for this conversation
        if use_conversation_cache:
            compiled_graph = self.graph_cache.get_cached_graph_for_conversation(conversation_id)
        
        # If no cached graph found, create or get from agent config cache
        if compiled_graph is None:
            compiled_graph = self.graph_cache.get_or_store_compiled_graph(
                agents, 
                lambda agents: self.graph_builder.build_graph(agents)
            )
            # Cache the conversation -> agent config mapping
            if use_conversation_cache:
                self.graph_cache.cache_conversation_agents(conversation_id, agents)

        input = {
            "messages": [
                ("user", f"Answer this question: {message}")
            ]
        }

        config = {
            "configurable": {
                "user_id": user_id,
                "thread_id": conversation_id,
            },
            "recursion_limit": 100,
        }
        
        try:
            for chunk, _ in compiled_graph.stream(input, config=config, stream_mode="messages"):
                yield json.dumps(chunk.model_dump(), ensure_ascii=False)
        except Exception as e:
            yield json.dumps({"content": str(e)}, ensure_ascii=False)

    def clear_conversation_cache(self, conversation_id: str) -> bool:
        """
        Clear cached graph for a specific conversation.
        
        :param conversation_id: The conversation ID to clear cache for.
        :return: True if cache was cleared, False if no cache existed.
        """
        return self.graph_cache.clear_conversation_cache(conversation_id)

    def clear_all_cache(self) -> None:
        """
        Clear all cached compiled graphs and conversation mappings.
        """
        self.graph_cache.clear_all_cache()

    def force_cleanup_expired_cache(self) -> int:
        """
        Manually trigger cleanup of expired cache entries.
        
        :return: Number of expired entries removed.
        """
        return self.graph_cache.force_cleanup_expired_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current cache state including expiration info.
        
        :return: Dictionary containing cache statistics.
        """
        return self.graph_cache.get_cache_stats()
    
completion_action = CompletionAction()