import json
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
    ChunkType,
    ChunkContent,
    StreamingStatus,
    ResponseMetadata,
    Attachment,
    Metadata,
)
from internal.graph.builder.graph import GraphBuilder
from langfuse.langchain import CallbackHandler

# Constants and Configuration
logger = get_logger()

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
        self.langfuse_handler = CallbackHandler()
        
        # Conversation-level locks to prevent concurrent processing of same conversation
        self._conversation_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_cleanup_lock = threading.Lock()

    def _create_error_chunk(self, error_message: str) -> StreamingChunk:
        """Create an error StreamingChunk."""
        return StreamingChunk(
            content=[
                ChunkContent(
                    type=ChunkType.ERROR,
                    value="Error during processing, please try again.",
                    agent=PRIMARY_AGENT,
                    index=0,
                    metadata={}
                )
            ],
            response_metadata=ResponseMetadata(status=StreamingStatus.FINISHED)
        )
        
    def _create_final_chunk(self) -> Optional[StreamingChunk]:
        """Create and send final completion chunk."""
        return StreamingChunk(
            content=[
                ChunkContent(
                    type=ChunkType.TEXT,
                    value="",
                    agent=PRIMARY_AGENT,
                    index=0,
                    metadata={}
                )
            ],
            response_metadata=ResponseMetadata(status=StreamingStatus.FINISHED)
        )
    
    def _extract_tool_outputs(self, chunk, agent_name: str) -> List[ChunkContent]:
        chunks = []
        if chunk.type == "tool" and type(chunk.content) is str:
            if chunk.name.startswith("zoan_internal") or chunk.name.startswith("transfer_back_"):
                return chunks
            
            tool_output = (
"""
```python
{tool_name} ->:
{tool_output}
```
""".format(tool_name=chunk.name, tool_output=chunk.content)
            )
            chunks.append(ChunkContent(
                type=ChunkType.TEXT,
                value=tool_output,
                agent=agent_name,
                index=0,
                metadata={}
            ))
            if chunk.name == "build_source" and chunk.status == 'success':
                # Special handling for build_source tool to include game URL
                build_response = json.loads(chunk.content)
                game_version = build_response.get("version")
                game_url = build_response.get("game_url")
                
                if game_url and game_version and build_response.get("status") != "failed":
                    logger.debug("Send game signal chunk")
                    chunks.append(ChunkContent(
                        type=ChunkType.GAME_SIGNAL,
                        value="",
                        agent=agent_name,
                        index=0,
                        metadata={
                            "game_url": game_url,
                            "game_version": game_version
                        }
                    ))
                
        return chunks

    def _extract_text_content(self, chunk, agent_name: str) -> List[ChunkContent]:
        """Extract text content from chunk's additional kwargs."""
        if chunk.type == "AIMessageChunk" and type(chunk.content) is list:
            content_list = []
            for message in chunk.content:
                if type(message) is dict:
                    if message.get("type") == "text":
                        content_list.append(ChunkContent(
                            type=ChunkType.TEXT,
                            value=message.get("text", ""),
                            agent=agent_name,
                            index=0,
                            metadata={}
                        ))
                    elif message.get("type") == "reasoning":
                        reasoning_text = ""
                        summaries = message.get("summary", [])
                        for summary in summaries:
                            if summary.get("type") == "summary_text":
                                reasoning_text += summary.get("text", "")
                                
                        content_list.append(ChunkContent(
                            type=ChunkType.TEXT,
                            value=reasoning_text,
                            agent=agent_name,
                            index=0,
                            metadata={}
                        ))
            return content_list
        return []

    def _extract_message_content(self, chunk, agent_name: str) -> List[ChunkContent]:
        """Extract message content from chunk."""
        content_list = []
        for message in chunk.content:
            if isinstance(message, dict) and message.get("type") == "text":
                content_list.append(ChunkContent(
                    type=ChunkType.TEXT,
                    value=message.get("text", ""),
                    agent=agent_name,
                    index=0,
                    metadata={}
                ))
        return content_list

    def _convert_chunk_content(self, chunk, agent_name: str) -> StreamingChunk:
        """Convert chunk content to the StreamingChunk model."""
        content_list = []
        
        # Extract tool outputs
        content_list.extend(self._extract_tool_outputs(chunk, agent_name))
        
        # Extract text content
        content_list.extend(self._extract_text_content(chunk, agent_name))
                
        response_metadata = ResponseMetadata(
            status=chunk.response_metadata.get("status", "")
        )
        
        return StreamingChunk(
            content=content_list,
            response_metadata=response_metadata
        )

    def _process_chunk(self, agent_name: str, chunk) -> StreamingChunk:
        """Process chunk content and extract annotations."""
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

    def _create_graph_config(
        self, 
        user_id: str, 
        conversation_id: str, 
        auth_token: str = ""
    ) -> Dict[str, Any]:
        """
        Create configuration for graph execution.
        
        Args:
            user_id: ID of the user
            conversation_id: ID of the conversation
            auth_token: Authorization token for webhook calls (optional)
            
        Returns:
            Configuration dictionary for graph execution
        """
        return {
            "configurable": {
                "user_id": user_id,
                "thread_id": conversation_id,
                "auth_token": auth_token,
            },
            "callbacks": [self.langfuse_handler],
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


