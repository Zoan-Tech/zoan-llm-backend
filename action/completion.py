import os
import json
from config.logging import get_logger
from typing import Dict, Any

from langfuse import observe

from model import (
    AgentConfig,
    StreamingChunk,
    ChunkContent,
    ResponseMetadata,
)
from graph.builder import GraphBuilder
from services.kafka_service import KafkaClient
from utils.enums import *
from action.minio_game_builder import MinioGameBuilder

logger = get_logger()
PRIMARY_AGENT = "supervisor"
FINISHED_STATUS = "finished"
AGENT_COMPLETED_STATUS = "completed"
KAFKA_TOPIC_RESPONSE = "KAFKA_TOPIC_RESPONSE"

class CompletionAction:
    """Handles completion actions using LangGraph and a Postgres database."""

    def __init__(self):
        """
        Initialize the CompletionAction with caching support.
        
        :param cache_ttl_seconds: TTL for cache entries. Defaults to 15 minutes if None.
        """
        self.graph_builder = GraphBuilder()
        self.minio_builder = MinioGameBuilder()
        self.kafka_client = KafkaClient(topics=[os.getenv(KAFKA_TOPIC_RESPONSE)])
        
    def _convert_chunk_content(self, chunk, agent_name) -> StreamingChunk:
        """
        Convert chunk content to the StreamingChunk model.
        
        :param chunk: The chunk of data to convert.
        :return: Converted StreamingChunk object.
        """
        content_list = []                            
        if "reasoning" in chunk.additional_kwargs:
            for summary in chunk.additional_kwargs["reasoning"].get("summary", []):
                content_list.append(ChunkContent(
                    type="text",
                    text=summary.get("text", ""),
                    agent=agent_name,
                    index=summary.get("index", 0),
                    url="",
                ))
            
        for message in chunk.content:
            if type(message) == dict and message.get("type") == "text":
                content_list.append(ChunkContent(
                    type=message.get("type"),
                    text=message.get("text", ""),
                    agent=agent_name,
                    index=message.get("index", 0),
                    url=message.get("url", ""),
                ))
                
        response_metadata = ResponseMetadata(
            status=chunk.response_metadata.get("status", "")
        )
        
        return StreamingChunk(
            content=content_list,
            response_metadata=response_metadata
        )
        
    def _postprocess_chunk_content(self, agent_name, chunk, annotation) -> StreamingChunk:
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

        return self._convert_chunk_content(chunk, agent_name)
                
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
                "code": None,  # To be filled if found in annotations
            },
            "recursion_limit": 100,
        }
        annotation = {}
        last_chunk = None
        
        try:
            logger.info("Sending completion response: %s", conversation_id)
            for agent, chunk in compiled_graph.stream(input, config=config, stream_mode="messages", subgraphs=True):                    
                # Post-process chunk content to extract container ID if present
                agent_name = agent[0].split(":")[0] if len(agent) > 0 else PRIMARY_AGENT
                logger.debug("Chunks received from agent %s: %s", agent_name, chunk)
                    
                streaming_chunk: StreamingChunk = self._postprocess_chunk_content(agent_name, chunk[0], annotation)
                    
                # yield json.dumps(chunk[0].model_dump())
                self.kafka_client.produce(
                    topic=os.getenv(KAFKA_TOPIC_RESPONSE), 
                    key=conversation_id, 
                    value=streaming_chunk.model_dump()
                )
                # Batch messages for better performance, only flush at end
                # self.kafka_client.flush(timeout=0.1)
                last_chunk = streaming_chunk
            
            logger.info("Sent completion response: %s", conversation_id)
                
        except Exception as e:
            logger.error(f"Error during graph streaming: {str(e)}")
            error_object = {
                "type": "error",
                "content": [
                    {
                        "type": "text",
                        "text": f"Error during processing: {str(e)}",
                        "agent": PRIMARY_AGENT
                    }
                ]
            }
            self.kafka_client.produce(
                topic=os.getenv(KAFKA_TOPIC_RESPONSE),
                key=conversation_id,
                value=error_object,
            )
        
        # Build game files only if we have a valid container ID and no exception occurred
        container_id = annotation.get("container_id")
        if container_id:
            try:
                minio_prefix = await self.minio_builder.build_openai_game_file(
                    container_id, 
                    thread_id=conversation_id
                )
                chunk_content = ChunkContent(
                    type="game-signal",
                    text="",
                    agent=PRIMARY_AGENT,
                    index=0,
                    url=f"builds/{minio_prefix}/index.html",
                    game_version=str(minio_prefix.split('/')[-1])
                )
                game_built_object = StreamingChunk(
                    content=[chunk_content],
                    response_metadata=ResponseMetadata(status=AGENT_COMPLETED_STATUS)
                )
                self.kafka_client.produce(
                    topic=os.getenv(KAFKA_TOPIC_RESPONSE),
                    key=conversation_id,
                    value=game_built_object.model_dump()
                )
            except Exception as e:
                logger.error(f"Failed to build game files for container {container_id}: {str(e)}")
                # Don't re-raise here as the main stream has already completed
                    # After the stream ends, send a final chunk indicating completion
        if last_chunk:
            last_chunk.response_metadata.status = FINISHED_STATUS
            self.kafka_client.produce(
                topic=os.getenv(KAFKA_TOPIC_RESPONSE), 
                key=conversation_id, 
                value=last_chunk.model_dump()
            )
            self.kafka_client.flush(timeout=0.1)

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