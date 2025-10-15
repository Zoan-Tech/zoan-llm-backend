from datetime import datetime
import base64
import httpx
import asyncio
import threading
from collections import defaultdict
from config.logging import get_logger
from typing import Dict, Any, List, Tuple, Optional

from model import (
    StreamingChunk,
    ChunkContent,
    ResponseMetadata,
    Attachment,
    Metadata,
)
from graph.builder.graph import GraphBuilder
from action.minio_processor.games import games_processor

# Constants and Configuration
logger = get_logger()

class StreamingStatus:
    FINISHED = "finished"
    COMPLETED = "completed"

# Agent and Status Constants
PRIMARY_AGENT = "supervisor"

# Processing Configuration
DEFAULT_RECURSION_LIMIT = 100


class BaseCompletionAction:
    """
    Base class for completion actions using LangGraph.
    
    Contains shared initialization and helper methods used by both
    Kafka and gRPC completion implementations.
    """
    
    def __init__(self):
        """Initialize the BaseCompletionAction with required services."""
        self.graph_builder = GraphBuilder()
        self.minio_builder = games_processor
        
        # Conversation-level locks to prevent concurrent processing of same conversation
        self._conversation_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_cleanup_lock = threading.Lock()

    def _create_error_chunk(self, error_message: str) -> StreamingChunk:
        """Create an error StreamingChunk."""
        return StreamingChunk(
            content=[
                ChunkContent(
                    type="text",
                    text=f"Error during processing: {error_message}",
                    agent=PRIMARY_AGENT,
                    index=0,
                    url="",
                )
            ],
            response_metadata=ResponseMetadata(status=StreamingStatus.FINISHED)
        )
        
    def _create_final_chunk(self, last_chunk: StreamingChunk) -> Optional[StreamingChunk]:
        """Create and send final completion chunk."""
        if last_chunk:
            last_chunk.response_metadata.status = StreamingStatus.FINISHED
            return last_chunk
        return None

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
                        
        if chunk.additional_kwargs.get("tool_outputs"):
            for tool_output in chunk.additional_kwargs["tool_outputs"]:
                if tool_output.get("type") == "code_interpreter_call":
                    annotation["app"]["latest"] = {
                        "code": tool_output.get("code"),
                        "container_id": tool_output.get("container_id")
                    }

    def _process_chunk(self, agent_name: str, chunk, annotation: Dict[str, Any]) -> StreamingChunk:
        """Process chunk content and extract annotations."""
        self._extract_annotations(chunk, annotation)
        return self._convert_chunk_content(chunk, agent_name)
    
    def _graph_image_input(self, attachments: List[Attachment]) -> List[Dict[str, Any]]:
        """Create input configuration for the graph with image attachments."""
        # TODO: Add caching for images to avoid repeated downloads
        attachment_input = []
        for attachment in attachments:
            try:
                image_data = base64.b64encode(httpx.get(attachment.url).content).decode("utf-8")
                
                attachment_input.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{attachment.mime_type};base64,{image_data}",
                    }
                })
            except Exception as e:
                logger.error(f"Failed to fetch or encode image from {attachment.url}: {str(e)}")
                continue
            
        return attachment_input

    def _create_graph_input(self, message: str, attachments: Optional[List[Attachment]] = None, metadata: Metadata = Metadata()) -> Dict[str, Any]:
        """Create input configuration for the graph."""
        graph_input = { 
            "messages": [
                ("user", "[{datetime}] - {message}".format(datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message=message))
            ]
        }
        
        # Include attachments if available
        if attachments and len(attachments) > 0:
            attachment_input = self._graph_image_input(attachments)
            
            if len(attachment_input) > 0:
                graph_input["messages"].append(
                    ("user", attachment_input)
                )
        
        # Include console logs if available
        if metadata.console_logs != "":
            graph_input["messages"].append(
                ("user", f"Current console logs:\n{metadata.console_logs}")
            )
        
        return graph_input

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
    
    async def _get_conversation_messages(self, config: Dict[str, Any]) -> List:
        """
        Get conversation messages from checkpoint.
        
        Args:
            config: Graph configuration containing thread_id
            
        Returns:
            List of message objects from the conversation history
        """
        try:
            # Run synchronous DB operation in thread pool to avoid gRPC fork warnings
            checkpoint_tuple = await asyncio.to_thread(
                self.graph_builder.memory.saver.get_tuple,
                config=config
            )
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                messages = checkpoint_tuple.checkpoint.get('channel_values', {}).get('messages', [])
                return messages
            return []
        except Exception as e:
            logger.error(f"[BaseCompletionAction] Error retrieving conversation messages: {str(e)}")
            return []

    def _extract_agent_name(self, agent: Tuple) -> str:
        """Extract agent name from agent tuple."""
        return agent[0].split(":")[0] if len(agent) > 0 else PRIMARY_AGENT

    async def _extract_app_versions(self, annotation: Dict[str, Any], config: dict) -> None:
        """Extract all app versions from checkpoint history."""
        annotation["app"] = {}
        # Run synchronous DB operation in thread pool to avoid gRPC fork warnings
        checkpoint_tuple = await asyncio.to_thread(
            self.graph_builder.memory.saver.get_tuple,
            config=config
        )
        
        game_version = 1
        for chunk in checkpoint_tuple.checkpoint['channel_values']["messages"]:
            if chunk.additional_kwargs.get("tool_outputs"):
                for tool_output in chunk.additional_kwargs["tool_outputs"]:
                    if tool_output.get("type") == "code_interpreter_call":
                        annotation["app"][f"version_{game_version}"] = {
                            "code": tool_output.get("code"),
                            "container_id": tool_output.get("container_id")
                        }
                        game_version += 1

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
