import os
from config.logging import get_logger
from typing import Dict, Any, List, Tuple, Optional

from langgraph.graph.state import CompiledStateGraph

from langfuse import observe

from model import (
    AgentConfig,
    StreamingChunk,
    ChunkContent,
    ResponseMetadata,
)
from graph.builder import GraphBuilder
from services.kafka_service import KafkaProducer
from utils.enums import *
from action.minio_processor.games import DEFAULT_GAMES_PROCESSOR

# Constants and Configuration
logger = get_logger()

# Agent and Status Constants
PRIMARY_AGENT = "supervisor"
FINISHED_STATUS = "finished"
AGENT_COMPLETED_STATUS = "completed"

# Kafka Configuration
DEFAULT_KAFKA_TOPIC_COMPLETION_RESPONSE = "llm.channel.response"

# Processing Configuration
DEFAULT_RECURSION_LIMIT = 100
KAFKA_FLUSH_TIMEOUT = 0.1

class CompletionAction:
    """Handles completion actions using LangGraph and Kafka messaging."""
    
    def __init__(self):
        """Initialize the CompletionAction with required services."""
        self.kafka_topic_response = os.getenv(
            SecretEnum.KAFKA_TOPIC_RESPONSE.value,
            DEFAULT_KAFKA_TOPIC_COMPLETION_RESPONSE
        )
        self.graph_builder = GraphBuilder()
        self.minio_builder = DEFAULT_GAMES_PROCESSOR
        self.kafka_producer = KafkaProducer()

    def _send_error_message(self, conversation_id: str, error_message: str) -> None:
        """Send error message to Kafka topic."""
        error_object = {
            "content": [
                {
                    "type": "text",
                    "text": f"Error during processing: {error_message}",
                    "agent": PRIMARY_AGENT,
                    "index": 0,
                    "url": "",
                }
            ],
            "response_metadata": {
                "status": FINISHED_STATUS
            }
        }
        self.kafka_producer.produce(
            topic=self.kafka_topic_response,
            key=conversation_id,
            value=error_object,
        )

    def _send_streaming_chunk(self, conversation_id: str, streaming_chunk: StreamingChunk) -> None:
        """Send streaming chunk to Kafka topic."""
        self.kafka_producer.produce(
            topic=self.kafka_topic_response,
            key=conversation_id,
            value=streaming_chunk.model_dump()
        )
        
    def _extract_reasoning_content(self, chunk, agent_name: str) -> List[ChunkContent]:
        """Extract reasoning content from chunk's additional kwargs."""
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
        return content_list

    def _extract_message_content(self, chunk, agent_name: str) -> List[ChunkContent]:
        """Extract message content from chunk."""
        content_list = []
        for message in chunk.content:
            if isinstance(message, dict) and message.get("type") == "text":
                content_list.append(ChunkContent(
                    type=message.get("type"),
                    text=message.get("text", ""),
                    agent=agent_name,
                    index=message.get("index", 0),
                    url=message.get("url", ""),
                ))
        return content_list

    def _convert_chunk_content(self, chunk, agent_name: str) -> StreamingChunk:
        """Convert chunk content to the StreamingChunk model."""
        content_list = []
        
        # Extract reasoning content
        content_list.extend(self._extract_reasoning_content(chunk, agent_name))
        
        # Extract message content
        content_list.extend(self._extract_message_content(chunk, agent_name))
                
        response_metadata = ResponseMetadata(
            status=chunk.response_metadata.get("status", "")
        )
        
        return StreamingChunk(
            content=content_list,
            response_metadata=response_metadata
        )

    def _extract_annotations(self, chunk, annotation: Dict[str, Any]) -> None:
        """Extract annotations from chunk content (modifies annotation dict in-place)."""
        logger.debug(f"Extracted annotations from chunk: {chunk}")
        if type(chunk.content) is list:    
            for message in chunk.content:
                if not isinstance(message, dict) or "annotations" not in message:
                    continue
                    
                for ann in message["annotations"]:
                    if "container_id" in ann:
                        annotation.update(ann)
        
        if chunk.additional_kwargs.get("tool_outputs"):
            for tool_output in chunk.additional_kwargs["tool_outputs"]:
                if tool_output.get("type") == "code_interpreter_call":
                    annotation.update({
                        "code": tool_output.get("code", "")
                    })
                    if annotation.get("container_id") is None and tool_output.get("container_id"):
                        annotation.update({
                            "container_id": tool_output.get("container_id")
                        })

    def _process_chunk(self, agent_name: str, chunk, annotation: Dict[str, Any]) -> StreamingChunk:
        """Process chunk content and extract annotations."""
        self._extract_annotations(chunk, annotation)
        return self._convert_chunk_content(chunk, agent_name)

    def _create_graph_input(self, message: str) -> Dict[str, Any]:
        """Create input configuration for the graph."""
        return {
            "messages": [
                ("user", f"Process this question: {message}")
            ]
        }

    def _create_graph_config(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        """Create configuration for graph execution."""
        return {
            "configurable": {
                "user_id": user_id,
                "thread_id": conversation_id,
                "code": None,  # To be filled if found in annotations
            },
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
        }

    def _extract_agent_name(self, agent: Tuple) -> str:
        """Extract agent name from agent tuple."""
        return agent[0].split(":")[0] if len(agent) > 0 else PRIMARY_AGENT

    async def _process_graph_stream(
        self, 
        compiled_graph: CompiledStateGraph, 
        input_data: Dict[str, Any], 
        config: Dict[str, Any], 
        conversation_id: str
    ) -> Tuple[Optional[StreamingChunk], Dict[str, Any]]:
        """Process the graph stream and return last chunk and annotations."""
        annotation = {}
        last_chunk = None
        
        for agent, chunk in compiled_graph.stream(input_data, config=config, stream_mode="messages", subgraphs=True):                    
            agent_name = self._extract_agent_name(agent)
                
            streaming_chunk = self._process_chunk(agent_name, chunk[0], annotation)
            self._send_streaming_chunk(conversation_id, streaming_chunk)
            last_chunk = streaming_chunk
        
        return last_chunk, annotation

    async def _build_game_files(self, container_id: str, conversation_id: str, annotation: dict) -> None:
        """Build game files if container ID is available."""
        try:
            logger.info(f"Building game files for container {container_id} in conversation {conversation_id}")
            minio_prefix = await self.minio_builder.build_openai_game_file(
                container_id, 
                thread_id=conversation_id,
                annotation=annotation   
            )
            
            chunk_content = ChunkContent(
                type="game-signal",
                text="",
                agent=PRIMARY_AGENT,
                index=0,
                url=f"{minio_prefix}/index.html",
                game_version=str(minio_prefix.split('/')[-1])
            )
            
            game_built_object = StreamingChunk(
                content=[chunk_content],
                response_metadata=ResponseMetadata(status=AGENT_COMPLETED_STATUS)
            )
            
            self._send_streaming_chunk(conversation_id, game_built_object)
            
        except Exception as e:
            logger.error(f"Failed to build game files for container {container_id}: {str(e)}")

    def _send_final_chunk(self, last_chunk: StreamingChunk, conversation_id: str) -> None:
        """Send final completion chunk and flush producer."""
        if last_chunk:
            last_chunk.response_metadata.status = FINISHED_STATUS
            self._send_streaming_chunk(conversation_id, last_chunk)
            self.kafka_producer.flush(timeout=KAFKA_FLUSH_TIMEOUT)

    @observe(as_type="generation")
    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: List[AgentConfig],
    ) -> None:
        """Create a completion using the specified model and messages."""
        compiled_graph = self.graph_builder.get_compiled_graph(agents)
        input_data = self._create_graph_input(message)
        config = self._create_graph_config(user_id, conversation_id)
        
        try:
            last_chunk, annotation = await self._process_graph_stream(
                compiled_graph, input_data, config, conversation_id
            )
            
            logger.info("Sent completion response: %s", conversation_id)
            
            # Build game files if container ID is available
            container_id = annotation.get("container_id")
            if container_id or annotation.get("code"):
                await self._build_game_files(container_id, conversation_id, annotation)
            
            # Send final completion chunk
            self._send_final_chunk(last_chunk, conversation_id)
                
        except Exception as e:
            logger.error(f"Error during graph streaming: {str(e)}")
            self._send_error_message(conversation_id, str(e))

    def clear_all_cache(self) -> None:
        """Clear all cached compiled graphs and conversation mappings."""
        self.graph_builder.graph_cache.clear_all_cache()

    def force_cleanup_expired_cache(self) -> int:
        """
        Manually trigger cleanup of expired cache entries.
        
        Returns:
            Number of expired entries removed.
        """
        return self.graph_builder.graph_cache.force_cleanup_expired_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current cache state including expiration info.
        
        Returns:
            Dictionary containing cache statistics.
        """
        return self.graph_builder.graph_cache.get_cache_stats()
    
completion_action = CompletionAction()