import os
import json
from config.logging import get_logger
from typing import Dict, Any

from langfuse import observe

from model import AgentConfig
from graph.builder import GraphBuilder
from services.kafka_service import KafkaClient
from utils.enums import *
from action.minio_game_builder import MinioGameBuilder

logger = get_logger()

class CompletionAction:
    """Handles completion actions using LangGraph and a Postgres database."""

    def __init__(self):
        """
        Initialize the CompletionAction with caching support.
        
        :param cache_ttl_seconds: TTL for cache entries. Defaults to 15 minutes if None.
        """
        self.graph_builder = GraphBuilder()
        self.minio_builder = MinioGameBuilder()
        self.kafka_client = KafkaClient(topics=[os.getenv("KAFKA_TOPIC_RESPONSE")])
        
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

    @observe(as_type="generation")
    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: list[AgentConfig],
    ):
        """
        Create a completion using the specified model and messages.
        
        :param user_id: The user ID for the completion.
        :param conversation_id: The conversation ID for thread management.
        :param message: The user message to process.
        :param agents: List of agent configurations.
        :return: The response from the chat model.
        """
        compiled_graph = self.graph_builder.get_compiled_graph(agents)

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
            logger.info("Sending completion response: %s", container_id)
            for agent, chunk in compiled_graph.stream(input, config=config, stream_mode="messages", subgraphs=True):                    
                # Post-process chunk content to extract container ID if present
                agent_name = agent[0] if len(agent) > 0 else "supervisor"
                self._postprocess_chunk_content(agent_name, chunk[0], annotation)
                self.kafka_client.produce(
                    topic=os.getenv("KAFKA_TOPIC_RESPONSE"), 
                    key=conversation_id, 
                    value=chunk[0].model_dump()
                )
                # Flush immediately for streaming to ensure low latency
                self.kafka_client.flush(timeout=0.1)
                # yield json.dumps(chunk[0].model_dump(), ensure_ascii=False)
                
            logger.info("Sent completion response: %s", container_id)
                
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
            self.kafka_client.produce(os.getenv("KAFKA_TOPIC_RESPONSE"), json.dumps(error_object, ensure_ascii=False))
            # yield json.dumps(error_object, ensure_ascii=False)
        
        # Build game files only if we have a valid container ID and no exception occurred
        container_id = annotation.get("container_id")
        if container_id:
            try:
                await self.minio_builder.build_openai_game_file(
                    container_id, 
                    thread_id=conversation_id
                )
                game_built_object = [{
                    "type": "game-signal",
                    "text": "success",
                    "agent": "",
                    "url": f"builds/{conversation_id}/index.html"
                }]
                self.kafka_client.produce(os.getenv("KAFKA_TOPIC_RESPONSE"), json.dumps({
                    "type": "game-built",
                    "content": game_built_object
                }, ensure_ascii=False))
                # yield json.dumps({
                #     "type": "game-built",
                #     "content": game_built_object
                # }, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to build game files for container {container_id}: {str(e)}")
                # Don't re-raise here as the main stream has already completed

    def clear_all_cache(self) -> None:
        """
        Clear all cached compiled graphs and conversation mappings.
        """
        self.graph_builder.graph_cache.clear_all_cache()

    def force_cleanup_expired_cache(self) -> int:
        """
        Manually trigger cleanup of expired cache entries.
        
        :return: Number of expired entries removed.
        """
        return self.graph_builder.graph_cache.force_cleanup_expired_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current cache state including expiration info.
        
        :return: Dictionary containing cache statistics.
        """
        return self.graph_builder.graph_cache.get_cache_stats()
    
completion_action = CompletionAction()