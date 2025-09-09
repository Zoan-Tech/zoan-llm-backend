import json
import hashlib
import time
from config.logging import get_logger
from typing import Dict, Any, Tuple, Optional
from langgraph.graph.state import CompiledStateGraph

from model import AgentConfig
from .mem_cache import MemCache

logger = get_logger()

DEFAULT_CACHE_TTL_SECONDS = 1800  # 30 minutes
class GraphCache(MemCache[str, CompiledStateGraph]):
    """
    Enhanced graph cache that handles agent configuration caching and analytics.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        """
        Initialize the enhanced graph cache.
        
        :param ttl_seconds: Time-to-live for cache entries in seconds. Defaults to 15 minutes.
        """
        super().__init__(ttl_seconds=ttl_seconds, cache_name="GraphCache")
        
        # Agent configuration registry for detailed tracking
        # Format: {config_hash: {agents_summary, first_seen, last_used, usage_count}}
        self._agent_config_registry: Dict[str, Dict[str, Any]] = {}

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

    def _cleanup_agent_registry(self) -> int:
        """
        Clean up agent registry entries that no longer have active cache entries.
        
        :return: Number of registry entries removed.
        """
        # Get currently active config hashes from main cache
        active_hashes = set(self.get_cache_keys())
        
        # Remove registry entries for inactive hashes
        inactive_hashes = set(self._agent_config_registry.keys()) - active_hashes
        removed_count = len(inactive_hashes)
        
        for hash_key in inactive_hashes:
            del self._agent_config_registry[hash_key]
        
        return removed_count

    def _update_agent_registry(self, agents: list[AgentConfig], config_hash: str, is_new: bool = False):
        """
        Update the agent configuration registry with usage statistics.
        
        :param agents: List of agent configurations.
        :param config_hash: Hash of the agent configuration.
        :param is_new: Whether this is a new configuration.
        """
        current_time = time.time()
        
        if config_hash not in self._agent_config_registry:
            # Create new registry entry
            agent_summary = self._create_agent_summary(agents)
            self._agent_config_registry[config_hash] = {
                "agents_summary": agent_summary,
                "first_seen": current_time,
                "last_used": current_time,
                "usage_count": 1,
                "is_compiled": not is_new
            }
        else:
            # Update existing entry
            self._agent_config_registry[config_hash]["last_used"] = current_time
            self._agent_config_registry[config_hash]["usage_count"] += 1
            if not is_new:
                self._agent_config_registry[config_hash]["is_compiled"] = True

    def _create_agent_summary(self, agents: list[AgentConfig]) -> Dict[str, Any]:
        """
        Create a summary of agent configurations for registry tracking.
        
        :param agents: List of agent configurations.
        :return: Summary dictionary.
        """
        return {
            "agent_count": len(agents),
            "agent_names": [agent.name for agent in agents],
            "models_used": list(set(agent.model for agent in agents)),
            "total_workflows": sum(len(agent.workflows) for agent in agents),
            "workflow_names": [
                workflow.name 
                for agent in agents 
                for workflow in agent.workflows
            ]
        }

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
        Enhanced method to get cached compiled graph or create new one with registry tracking.
        
        :param agents: List of agent configurations.
        :param graph_factory_func: Function to create a new compiled graph when needed.
        :return: The compiled graph (cached or newly created).
        """
        config_hash = self._generate_agent_config_hash(agents)
        
        # Check if we already have this graph cached
        existing_graph = self.get(config_hash)
        is_new_compilation = existing_graph is None
        
        # Update registry regardless of cache hit/miss
        self._update_agent_registry(agents, config_hash, is_new=is_new_compilation)
        
        if existing_graph:
            logger.info(f"[GraphCache] Cache HIT for config hash: {config_hash}")
            return existing_graph
        else:
            logger.info(f"[GraphCache] Cache MISS for config hash: {config_hash}, creating new graph")
        
        # Use the base MemCache functionality to get or create
        return self.get_or_create(agents, graph_factory_func=graph_factory_func)

    def clear_all_cache(self) -> None:
        """
        Clear all cached compiled graphs and agent registry.
        """
        logger.info("[GraphCache] Cleared all caches including agent registry")
        # Use base class method for main cache
        self.clear()
        # Clear agent registry
        self._agent_config_registry.clear()

    def force_cleanup_expired_cache(self) -> int:
        """
        Enhanced cleanup that includes agent registry cleanup.
        
        :return: Number of expired entries removed.
        """
        logger.info(f"[GraphCache] Cleanup removed {total_removed} entries (main: {main_cache_removed}, registry: {registry_removed})")
        
        # Clean up main cache using base class method
        main_cache_removed = self.force_cleanup()
        # Clean up agent registry
        registry_removed = self._cleanup_agent_registry()
        
        total_removed = main_cache_removed + registry_removed
        
        return total_removed

    def get_agent_config_analytics(self) -> Dict[str, Any]:
        """
        Get detailed analytics about cached agent configurations.
        
        :return: Dictionary containing agent configuration analytics.
        """
        current_time = time.time()
        
        analytics = {
            "total_unique_configs": len(self._agent_config_registry),
            "configs": {}
        }
        
        for config_hash, config_data in self._agent_config_registry.items():
            age_since_first_seen = current_time - config_data["first_seen"]
            age_since_last_used = current_time - config_data["last_used"]
            
            analytics["configs"][config_hash] = {
                "summary": config_data["agents_summary"],
                "first_seen": config_data["first_seen"],
                "last_used": config_data["last_used"],
                "usage_count": config_data["usage_count"],
                "age_since_first_seen_hours": age_since_first_seen / 3600,
                "age_since_last_used_hours": age_since_last_used / 3600,
                "is_compiled": config_data.get("is_compiled", True),
                "is_currently_cached": self.contains(config_hash)
            }
        
        return analytics

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Enhanced cache statistics including agent registry analytics.
        
        :return: Dictionary containing comprehensive cache statistics.
        """
        # Get base cache stats
        base_stats = self.get_stats()
        
        # Agent registry stats
        registry_stats = {
            "total_configs_tracked": len(self._agent_config_registry),
            "configs_currently_cached": sum(
                1 for config_hash in self._agent_config_registry.keys() 
                if self.contains(config_hash)
            ),
            "most_used_config": self._get_most_used_config(),
            "average_usage_per_config": (
                sum(data["usage_count"] for data in self._agent_config_registry.values()) / 
                len(self._agent_config_registry)
            ) if self._agent_config_registry else 0
        }
        
        # Combine all stats
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
            "agent_registry": registry_stats
        }

    def _get_most_used_config(self) -> Optional[Dict[str, Any]]:
        """
        Get the most frequently used agent configuration.
        
        :return: Information about the most used config, or None if no configs exist.
        """
        if not self._agent_config_registry:
            return None
            
        most_used = max(
            self._agent_config_registry.items(),
            key=lambda x: x[1]["usage_count"]
        )
        
        config_hash, config_data = most_used
        return {
            "config_hash": config_hash,
            "usage_count": config_data["usage_count"],
            "summary": config_data["agents_summary"]
        }

    @property
    def cache_size(self) -> Dict[str, int]:
        """
        Get the current size of the compiled graph cache.
        
        :return: Dictionary with cache sizes.
        """
        return {
            "compiled_graphs": self.size  # Use base class property
        }

DEFAULT_GRAPH_CACHE = GraphCache()