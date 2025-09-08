import os, json
import logging
import time
from typing import Dict, Any, Optional, List
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from langfuse import Langfuse, observe

from model import AgentConfig
from graph.builder import GraphBuilder
from module.client import ModuleClient
from cache import GraphCache
from utils.enums import *
from action.minio_game_builder import MinioGameBuilder

logger = logging.getLogger(__name__)

class CompletionAction:
    """Handles completion actions using LangGraph and a Postgres database."""

    def __init__(self, cache_ttl_seconds: Optional[int] = None):
        """
        Initialize the CompletionAction with caching support.
        
        :param cache_ttl_seconds: TTL for cache entries. Defaults to 15 minutes if None.
        """
        self._setup_graph_memory()
        self._setup_graph_builder()
        # Initialize the graph cache
        self.graph_cache = GraphCache(ttl_seconds=cache_ttl_seconds)
        self.minio_builder = MinioGameBuilder()
        
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
        
    def _postprocess_chunk_content(self, agent, chunk, annotation):
        """
        Post-process chunk content to extract container ID if present.
        
        :param agent: The agent instance.
        :param chunk: The chunk of data to process.
        :param annotation: Dictionary to store annotation data (modified in-place).
        :return: Processed chunk with container ID if found.
        """
        if type(chunk.content) == list and len(chunk.content) > 0:
            for message in chunk.content:
                if "annotations" in message:
                    annotations = message["annotations"]
                    for ann in annotations:
                        if "container_id" in ann:
                            annotation.update(ann)  # Update the dictionary in-place
                            
                elif "text" in message:
                    message.update({
                        "agent": agent
                    })
        elif type(chunk.content) == str:
            content = chunk.content
            chunk.content = [{
                "type": "text",
                "text": content,
                "agent": agent
            }]

    @observe(as_type="generation")
    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: list[AgentConfig],
        use_conversation_cache: bool = False,
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
        
        # Strategy 1: Try to get cached graph for this specific conversation
        if use_conversation_cache:
            logger.info(f"Attempting to retrieve cached graph for conversation: {conversation_id}")
            compiled_graph = self.graph_cache.get_cached_graph_for_conversation(conversation_id)
            if compiled_graph:
                logger.info(f"Using cached graph for conversation: {conversation_id}")
        
        # Strategy 2: Try to get cached graph based on agent configuration hash
        if compiled_graph is None:
            agent_config_hash = self.graph_cache._generate_agent_config_hash(agents)
            logger.info(f"Attempting to retrieve cached graph for agent config hash: {agent_config_hash}")
            
            # Check if we have a cached graph for this exact agent configuration
            compiled_graph = self.graph_cache.get_or_store_compiled_graph(
                agents, 
                lambda agents: self._build_graph_with_logging(agents, agent_config_hash)
            )
            
            # If we got a cached graph, link this conversation to the agent config
            if use_conversation_cache:
                logger.info(f"Caching conversation {conversation_id} -> agent config {agent_config_hash}")
                self.graph_cache.cache_conversation_agents(conversation_id, agents)
                
                # Store additional metadata for better cache management
                self._store_agent_config_metadata(conversation_id, agents, agent_config_hash)

        input = {
            "messages": [
                ("user", f"Process this question: {message}")
            ]
        }

        config = {
            "configurable": {
                "user_id": user_id,
                "thread_id": conversation_id,
            },
            "recursion_limit": 100,
        }
        annotation = {}
        
        try:
            for agent, chunk in compiled_graph.stream(input, config=config, stream_mode="messages", subgraphs=True):                    
                # Post-process chunk content to extract container ID if present
                self._postprocess_chunk_content(agent, chunk[0], annotation)
                yield json.dumps(chunk[0].model_dump(), ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error during graph streaming: {str(e)}")
            error_object = {
                "type": "error",
                "content": [
                    {
                        "type": "text",
                        "text": f"Error during processing: {str(e)}",
                        "agent": "supervisor"
                    }
                ]
            }
            yield json.dumps(error_object, ensure_ascii=False)
        
        # Build game files only if we have a valid container ID and no exception occurred
        container_id = annotation.get("container_id")
        if container_id:
            try:
                await self.minio_builder.build_openai_game_file(
                    container_id, 
                    extract_path=f"./games/{conversation_id}",
                    thread_id=conversation_id
                )
            except Exception as e:
                logger.error(f"Failed to build game files for container {container_id}: {str(e)}")
                # Don't re-raise here as the main stream has already completed

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

    def _build_graph_with_logging(self, agents: list[AgentConfig], config_hash: str):
        """
        Build graph with detailed logging for cache tracking.
        
        :param agents: List of agent configurations.
        :param config_hash: Hash of the agent configuration.
        :return: Compiled graph.
        """
        logger.info(f"Building new graph for agent config hash: {config_hash}")
        logger.debug(f"Agent count: {len(agents)}, Agent names: {[agent.name for agent in agents]}")
        
        try:
            compiled_graph = self.graph_builder.build_graph(agents)
            logger.info(f"Successfully built graph for config hash: {config_hash}")
            return compiled_graph
        except Exception as e:
            logger.error(f"Failed to build graph for config hash {config_hash}: {str(e)}")
            raise

    def _store_agent_config_metadata(self, conversation_id: str, agents: list[AgentConfig], config_hash: str):
        """
        Store additional metadata about agent configurations for better cache management.
        
        :param conversation_id: The conversation ID.
        :param agents: List of agent configurations.
        :param config_hash: Hash of the agent configuration.
        """
        try:
            # Create detailed metadata
            metadata = {
                "conversation_id": conversation_id,
                "config_hash": config_hash,
                "agent_count": len(agents),
                "agent_names": [agent.name for agent in agents],
                "agent_models": [agent.model for agent in agents],
                "workflow_count": sum(len(agent.workflows) for agent in agents),
                "cached_at": time.time()
            }
            
            # You could store this in a separate cache or database table for analytics
            logger.debug(f"Agent config metadata: {metadata}")
            
        except Exception as e:
            logger.warning(f"Failed to store agent config metadata: {str(e)}")
            # Don't fail the main operation for metadata issues

    def get_conversation_agent_config(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the agent configuration details for a conversation.
        
        :param conversation_id: The conversation ID.
        :return: Agent configuration details if found.
        """
        if conversation_id in self.graph_cache._conversation_agent_cache:
            config_hash, timestamp = self.graph_cache._conversation_agent_cache[conversation_id]
            return {
                "conversation_id": conversation_id,
                "config_hash": config_hash,
                "cached_at": timestamp,
                "age_seconds": time.time() - timestamp
            }
        return None

    def list_cached_agent_configs(self) -> Dict[str, Any]:
        """
        List all cached agent configurations with their details.
        
        :return: Dictionary containing all cached configurations.
        """
        return {
            "cache_stats": self.get_cache_stats(),
            "agent_analytics": self.graph_cache.get_agent_config_analytics(),
            "conversation_analytics": self.graph_cache.get_conversation_analytics()
        }

    def find_conversations_with_agent_config(self, config_hash: str) -> List[str]:
        """
        Find all conversations that use a specific agent configuration.
        
        :param config_hash: The configuration hash to search for.
        :return: List of conversation IDs using this configuration.
        """
        matching_conversations = []
        
        for conv_id, cache_data in self.graph_cache._conversation_agent_cache.items():
            if len(cache_data) == 2:  # Old format
                cached_hash, _ = cache_data
            else:  # New format
                cached_hash, _, _ = cache_data
                
            if cached_hash == config_hash:
                matching_conversations.append(conv_id)
        
        return matching_conversations

    def get_agent_config_details(self, agents: list[AgentConfig]) -> Dict[str, Any]:
        """
        Get detailed information about an agent configuration including cache status.
        
        :param agents: List of agent configurations.
        :return: Detailed configuration information.
        """
        config_hash = self.graph_cache._generate_agent_config_hash(agents)
        
        details = {
            "config_hash": config_hash,
            "is_cached": self.graph_cache.contains(config_hash),
            "agent_summary": self.graph_cache._create_agent_summary(agents),
            "conversations_using_config": self.find_conversations_with_agent_config(config_hash)
        }
        
        # Add registry information if available
        if config_hash in self.graph_cache._agent_config_registry:
            registry_data = self.graph_cache._agent_config_registry[config_hash]
            details.update({
                "first_seen": registry_data["first_seen"],
                "last_used": registry_data["last_used"],
                "usage_count": registry_data["usage_count"],
                "age_since_first_seen_hours": (time.time() - registry_data["first_seen"]) / 3600,
                "age_since_last_used_hours": (time.time() - registry_data["last_used"]) / 3600
            })
        
        return details

    def clear_agent_config_cache(self, agents: list[AgentConfig]) -> bool:
        """
        Clear cache for a specific agent configuration.
        
        :param agents: List of agent configurations.
        :return: True if cache was cleared, False if no cache existed.
        """
        config_hash = self.graph_cache._generate_agent_config_hash(agents)
        
        # Remove from main cache
        removed_from_main = self.graph_cache.remove(config_hash)
        
        # Remove from conversation mappings
        conversations_to_remove = self.find_conversations_with_agent_config(config_hash)
        for conv_id in conversations_to_remove:
            self.graph_cache.clear_conversation_cache(conv_id)
        
        # Remove from registry
        if config_hash in self.graph_cache._agent_config_registry:
            del self.graph_cache._agent_config_registry[config_hash]
        
        logger.info(f"Cleared cache for agent config {config_hash}, removed {len(conversations_to_remove)} conversation mappings")
        return removed_from_main or len(conversations_to_remove) > 0

    def optimize_cache(self) -> Dict[str, Any]:
        """
        Optimize the cache by removing expired entries and providing optimization recommendations.
        
        :return: Dictionary with optimization results and recommendations.
        """
        initial_stats = self.get_cache_stats()
        
        # Force cleanup
        removed_count = self.force_cleanup_expired_cache()
        
        final_stats = self.get_cache_stats()
        
        # Generate recommendations
        recommendations = []
        
        if final_stats["compiled_graphs"]["total"] > 10:
            recommendations.append("Consider reducing cache TTL to free up memory")
        
        if final_stats["conversation_mappings"]["expired"] > 0:
            recommendations.append("Schedule more frequent cleanup to remove expired mappings")
        
        if final_stats["agent_registry"]["configs_currently_cached"] < final_stats["agent_registry"]["total_configs_tracked"] * 0.5:
            recommendations.append("Many tracked configs are not cached - consider cleanup of registry")
        
        return {
            "optimization_performed": True,
            "entries_removed": removed_count,
            "initial_stats": initial_stats,
            "final_stats": final_stats,
            "recommendations": recommendations
        }
    
completion_action = CompletionAction()