"""
Enhanced API endpoints for agent configuration cache management.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from action.completion import completion_action
from model import AgentConfig

logger = logging.getLogger(__name__)
router = APIRouter()

class CacheStatsResponse(BaseModel):
    cache_stats: Dict[str, Any]
    agent_analytics: Dict[str, Any]
    conversation_analytics: Dict[str, Any]

class AgentConfigDetailsResponse(BaseModel):
    config_hash: str
    is_cached: bool
    agent_summary: Dict[str, Any]
    conversations_using_config: List[str]
    first_seen: Optional[float] = None
    last_used: Optional[float] = None
    usage_count: Optional[int] = None
    age_since_first_seen_hours: Optional[float] = None
    age_since_last_used_hours: Optional[float] = None

@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """
    Get comprehensive cache statistics including agent configurations.
    """
    try:
        stats = completion_action.list_cached_agent_configs()
        return CacheStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cache stats: {str(e)}")

@router.get("/cache/agent-analytics")
async def get_agent_config_analytics():
    """
    Get detailed analytics about agent configurations.
    """
    try:
        return completion_action.graph_cache.get_agent_config_analytics()
    except Exception as e:
        logger.error(f"Failed to get agent analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve agent analytics: {str(e)}")

@router.get("/cache/conversation-analytics")
async def get_conversation_analytics():
    """
    Get detailed analytics about conversation to agent config mappings.
    """
    try:
        return completion_action.graph_cache.get_conversation_analytics()
    except Exception as e:
        logger.error(f"Failed to get conversation analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversation analytics: {str(e)}")

@router.get("/cache/conversations/{config_hash}")
async def get_conversations_for_config(config_hash: str):
    """
    Get all conversations that use a specific agent configuration.
    
    :param config_hash: The agent configuration hash.
    """
    try:
        conversations = completion_action.find_conversations_with_agent_config(config_hash)
        return {
            "config_hash": config_hash,
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        logger.error(f"Failed to find conversations for config {config_hash}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find conversations: {str(e)}")

@router.post("/cache/agent-config/details", response_model=AgentConfigDetailsResponse)
async def get_agent_config_details(agents: List[AgentConfig]):
    """
    Get detailed information about an agent configuration.
    
    :param agents: List of agent configurations to analyze.
    """
    try:
        details = completion_action.get_agent_config_details(agents)
        return AgentConfigDetailsResponse(**details)
    except Exception as e:
        logger.error(f"Failed to get agent config details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get config details: {str(e)}")

@router.delete("/cache/conversation/{conversation_id}")
async def clear_conversation_cache(conversation_id: str):
    """
    Clear cache for a specific conversation.
    
    :param conversation_id: The conversation ID to clear cache for.
    """
    try:
        cleared = completion_action.clear_conversation_cache(conversation_id)
        return {
            "conversation_id": conversation_id,
            "cache_cleared": cleared,
            "message": "Cache cleared successfully" if cleared else "No cache found for conversation"
        }
    except Exception as e:
        logger.error(f"Failed to clear conversation cache for {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.delete("/cache/agent-config")
async def clear_agent_config_cache(agents: List[AgentConfig]):
    """
    Clear cache for a specific agent configuration.
    
    :param agents: List of agent configurations to clear cache for.
    """
    try:
        cleared = completion_action.clear_agent_config_cache(agents)
        config_hash = completion_action.graph_cache._generate_agent_config_hash(agents)
        return {
            "config_hash": config_hash,
            "cache_cleared": cleared,
            "message": "Cache cleared successfully" if cleared else "No cache found for configuration"
        }
    except Exception as e:
        logger.error(f"Failed to clear agent config cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.delete("/cache/all")
async def clear_all_cache():
    """
    Clear all cached data including graphs, conversations, and registry.
    """
    try:
        completion_action.clear_all_cache()
        return {
            "message": "All cache cleared successfully",
            "cleared": True
        }
    except Exception as e:
        logger.error(f"Failed to clear all cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.post("/cache/cleanup")
async def force_cache_cleanup():
    """
    Manually trigger cleanup of expired cache entries.
    """
    try:
        removed_count = completion_action.force_cleanup_expired_cache()
        return {
            "message": "Cache cleanup completed",
            "expired_entries_removed": removed_count
        }
    except Exception as e:
        logger.error(f"Failed to cleanup cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup cache: {str(e)}")

@router.post("/cache/optimize")
async def optimize_cache():
    """
    Optimize the cache and get recommendations.
    """
    try:
        optimization_results = completion_action.optimize_cache()
        return optimization_results
    except Exception as e:
        logger.error(f"Failed to optimize cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize cache: {str(e)}")

@router.get("/cache/config/{config_hash}/exists")
async def check_config_cached(config_hash: str):
    """
    Check if a specific agent configuration is currently cached.
    
    :param config_hash: The configuration hash to check.
    """
    try:
        is_cached = completion_action.graph_cache.contains(config_hash)
        registry_info = None
        
        if config_hash in completion_action.graph_cache._agent_config_registry:
            registry_data = completion_action.graph_cache._agent_config_registry[config_hash]
            registry_info = {
                "usage_count": registry_data["usage_count"],
                "last_used": registry_data["last_used"],
                "agents_summary": registry_data["agents_summary"]
            }
        
        return {
            "config_hash": config_hash,
            "is_cached": is_cached,
            "registry_info": registry_info
        }
    except Exception as e:
        logger.error(f"Failed to check config cache status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check cache status: {str(e)}")
