import json
import hashlib
import time
from typing import Dict, Any, Tuple, Optional
from langgraph.graph.state import CompiledStateGraph

from model import AgentConfig
from .mem_cache import MemCache


class GraphCache(MemCache[str, CompiledStateGraph]):
    """
    Handles caching of compiled graphs with TTL expiration to prevent OOM issues.
    Inherits from MemCache for common caching functionality.
    """

    def __init__(self, ttl_seconds: Optional[int] = None):
        """
        Initialize the graph cache.
        
        :param ttl_seconds: Time-to-live for cache entries in seconds. Defaults to 15 minutes.
        """
        super().__init__(ttl_seconds=ttl_seconds, cache_name="GraphCache")
        
        # Additional cache for conversation to agent config mapping with timestamps
        # Format: {conversation_id: (config_hash, timestamp)}
        self._conversation_agent_cache: Dict[str, Tuple[str, float]] = {}

    def _generate_cache_key(self, agents: list[AgentConfig], **kwargs) -> str:
        """
        Generate a cache key from agent configurations (required by MemCache).
        
        :param agents: List of agent configurations.
        :return: MD5 hash of the agent configurations.
        """
        return self._generate_agent_config_hash(agents)

    def _create_item(self, agents: list[AgentConfig], graph_factory_func=None, **kwargs) -> CompiledStateGraph:
        """
        Create a new compiled graph (required by MemCache).
        
        :param agents: List of agent configurations.
        :param graph_factory_func: Function to create the compiled graph.
        :return: New compiled graph.
        """
        if graph_factory_func is None:
            raise ValueError("graph_factory_func is required to create a compiled graph")
        return graph_factory_func(agents)

    def _cleanup_conversation_cache(self) -> int:
        """
        Remove expired entries from conversation cache.
        
        :return: Number of expired entries removed.
        """
        current_time = time.time()
        expired_conv_keys = [
            conv_id for conv_id, (_, timestamp) in self._conversation_agent_cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        removed_count = len(expired_conv_keys)
        for key in expired_conv_keys:
            del self._conversation_agent_cache[key]
        
        return removed_count

    def _generate_agent_config_hash(self, agents: list[AgentConfig]) -> str:
        """
        Generate a hash for the agent configurations to use as cache key.
        
        :param agents: List of agent configurations.
        :return: MD5 hash of the agent configurations.
        """
        # Create a stable string representation of the agent configs
        config_data = []
        for agent in agents:
            agent_dict = {
                'name': agent.name,
                'model': agent.model,
                'description': agent.description,
                'instruction': agent.instruction,
                'workflows': []
            }
            
            for workflow in agent.workflows:
                workflow_dict = {
                    'name': workflow.name,
                    'description': workflow.description,
                    'steps': []
                }
                
                for step in workflow.steps:
                    args = {k: v.model_dump() for k, v in step.args.items()} if step.args else {}
                    step_dict = {
                        'name': step.name,
                        'description': step.description,
                        'args': args,
                        'response_mapping': step.response_mapping
                    }
                    workflow_dict['steps'].append(step_dict)
                
                agent_dict['workflows'].append(workflow_dict)
            
            config_data.append(agent_dict)
        
        # Sort to ensure consistent hashing
        config_str = json.dumps(config_data, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def get_or_store_compiled_graph(
        self, 
        agents: list[AgentConfig], 
        graph_factory_func
    ) -> CompiledStateGraph:
        """
        Get cached compiled graph or create new one if not exists.
        Uses the base MemCache functionality.
        
        :param agents: List of agent configurations.
        :param graph_factory_func: Function to create a new compiled graph when needed.
        :return: The compiled graph (cached or newly created).
        """
        return self.get_or_create(agents, graph_factory_func=graph_factory_func)

    def cache_conversation_agents(self, conversation_id: str, agents: list[AgentConfig]) -> None:
        """
        Cache the mapping between conversation_id and agent configuration hash with timestamp.
        
        :param conversation_id: The conversation ID.
        :param agents: List of agent configurations.
        """
        config_hash = self._generate_agent_config_hash(agents)
        current_time = time.time()
        self._conversation_agent_cache[conversation_id] = (config_hash, current_time)

    def get_cached_graph_for_conversation(self, conversation_id: str) -> Optional[CompiledStateGraph]:
        """
        Get cached compiled graph for a conversation if exists and not expired.
        
        :param conversation_id: The conversation ID.
        :return: The compiled graph if found and not expired, None otherwise.
        """
        if conversation_id in self._conversation_agent_cache:
            config_hash, conv_timestamp = self._conversation_agent_cache[conversation_id]
            
            # Check if conversation mapping has expired
            if self._is_expired(conv_timestamp):
                del self._conversation_agent_cache[conversation_id]
                print(f"GraphCache: Expired conversation cache removed for: {conversation_id}")
                return None
            
            # Use base class method to get the compiled graph
            compiled_graph = self.get(config_hash)
            if compiled_graph is not None:
                print(f"GraphCache: Using cached graph for conversation: {conversation_id}")
                return compiled_graph
            else:
                # Graph expired or not found, remove conversation mapping
                del self._conversation_agent_cache[conversation_id]
                print(f"GraphCache: Expired cached graph, removed conversation mapping")
        
        return None

    def clear_conversation_cache(self, conversation_id: str) -> bool:
        """
        Clear cached graph for a specific conversation.
        
        :param conversation_id: The conversation ID to clear cache for.
        :return: True if cache was cleared, False if no cache existed.
        """
        if conversation_id in self._conversation_agent_cache:
            del self._conversation_agent_cache[conversation_id]
            print(f"GraphCache: Cleared conversation cache for: {conversation_id}")
            return True
        return False

    def clear_all_cache(self) -> None:
        """
        Clear all cached compiled graphs and conversation mappings.
        """
        # Use base class method for main cache
        self.clear()
        # Clear conversation cache
        self._conversation_agent_cache.clear()
        print("GraphCache: Cleared conversation mappings")

    def force_cleanup_expired_cache(self) -> int:
        """
        Manually trigger cleanup of expired cache entries.
        
        :return: Number of expired entries removed.
        """
        # Clean up main cache using base class method
        main_cache_removed = self.force_cleanup()
        # Clean up conversation cache
        conversation_cache_removed = self._cleanup_conversation_cache()
        
        return main_cache_removed + conversation_cache_removed

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current cache state including expiration info.
        Combines base cache stats with conversation cache stats.
        
        :return: Dictionary containing cache statistics.
        """
        # Get base cache stats
        base_stats = self.get_stats()
        
        # Calculate conversation cache stats
        current_time = time.time()
        non_expired_conversations = 0
        expired_conversations = 0
        conversation_ages = []
        
        for conv_id, (_, timestamp) in self._conversation_agent_cache.items():
            age_seconds = current_time - timestamp
            conversation_ages.append(age_seconds)
            if self._is_expired(timestamp):
                expired_conversations += 1
            else:
                non_expired_conversations += 1
        
        # Combine stats
        return {
            "cache_ttl_seconds": base_stats["cache_ttl_seconds"],
            "cache_ttl_minutes": base_stats["cache_ttl_minutes"],
            "compiled_graphs": {
                "total": base_stats["total_entries"],
                "non_expired": base_stats["non_expired_entries"],
                "expired": base_stats["expired_entries"],
                "avg_age_seconds": base_stats["avg_age_seconds"],
                "oldest_age_seconds": base_stats["oldest_age_seconds"],
                "cached_config_hashes": base_stats["cache_keys"]
            },
            "conversation_mappings": {
                "total": len(self._conversation_agent_cache),
                "non_expired": non_expired_conversations,
                "expired": expired_conversations,
                "avg_age_seconds": sum(conversation_ages) / len(conversation_ages) if conversation_ages else 0,
                "oldest_age_seconds": max(conversation_ages) if conversation_ages else 0,
                "cached_conversations": list(self._conversation_agent_cache.keys())
            }
        }

    @property
    def cache_size(self) -> Dict[str, int]:
        """
        Get the current size of both caches.
        
        :return: Dictionary with cache sizes.
        """
        return {
            "compiled_graphs": self.size,  # Use base class property
            "conversation_mappings": len(self._conversation_agent_cache)
        }
