import json
from datetime import datetime
import base64
import httpx
import asyncio
import threading
from collections import defaultdict
from io import BytesIO
from PIL import Image
from config.logging import get_logger
from typing import Dict, Any, List, Tuple, Optional

from model.completion import (
    StreamingChunk,
    ChunkType,
    ChunkContent,
    StreamingStatus,
    ResponseMetadata,
    Attachment,
    Metadata,
    AgentConfig
)
from internal.graph import GraphBuilder
from langfuse.langchain import CallbackHandler
from internal.document_processor import document_processor
from utils.const.multimodal import (
    IMAGE_MIME_TYPES,
    PDF_MIME_TYPES,
    AUDIO_MIME_TYPES,
    VIDEO_MIME_TYPES,
    DOCS_MIME_TYPES,
)

from langchain.messages import HumanMessage
from langgraph_supervisor.handoff import _normalize_agent_name

# Constants and Configuration
logger = get_logger()

# Agent and Status Constants
PRIMARY_AGENT = "supervisor"

# Processing Configuration
DEFAULT_RECURSION_LIMIT = 100

class CompletionInput:
    @classmethod
    def _process_image_attachment(cls, attachment: Attachment) -> Optional[list[dict[str, Any]]]:
        """Process image attachment and return data URL."""
        try:
            # Download image content
            image_content = httpx.get(attachment.url).content
            image_data = base64.b64encode(image_content).decode("utf-8")
            
            # Extract image dimensions
            image = Image.open(BytesIO(image_content))
            width, height = image.size
            
            return [
                {
                    "type": "text",
                    "text": "Image width: {}, height: {}".format(width, height)
                },
                {
                    "type": "image",
                    "base64": image_data,
                    "mime_type": attachment.mime_type,
                }
            ]
        except Exception as e:
            logger.error(f"Failed to fetch or encode image from {attachment.url}: {str(e)}")
            return None
        
    @classmethod
    def _process_pdf_attachment(cls, attachment: Attachment) -> Optional[dict[str, Any]]:
        """Process PDF attachment and return URL."""
        try:
            pdf_data = base64.b64encode(httpx.get(attachment.url).content).decode("utf-8")
            return {
                "type": "file",
                "base64": pdf_data,
                "mime_type": attachment.mime_type,
            }
        except Exception as e:
            logger.error(f"Failed to process PDF from {attachment.url}: {str(e)}")
            return None
        
    @classmethod
    def _process_audio_attachment(cls, attachment: Attachment) -> Optional[dict[str, Any]]:
        """Process audio attachment and return URL.""" 
        try:
            audio_data = base64.b64encode(httpx.get(attachment.url).content).decode("utf-8")
            return {
                "type": "audio",
                "base64": audio_data,
                "mime_type": attachment.mime_type,
            }
        except Exception as e:
            logger.error(f"Failed to process audio from {attachment.url}: {str(e)}")
            return None
        
    @classmethod
    def _process_video_attachment(cls, attachment: Attachment) -> Optional[dict[str, Any]]:
        """Process video attachment and return URL."""
        try:
            video_data = base64.b64encode(httpx.get(attachment.url).content).decode("utf-8")
            return {
                "type": "video",
                "base64": video_data,
                "mime_type": attachment.mime_type,
            }
        except Exception as e:
            logger.error(f"Failed to process video from {attachment.url}: {str(e)}")
            return None
    
    @classmethod
    def _process_doc_attachment(
        cls, 
        attachment: Attachment, 
        user_id: str = "", 
        conversation_id: str = ""
    ) -> Optional[dict[str, Any]]:
        """
        Process document attachment by storing it in Qdrant for later retrieval.
        
        Args:
            attachment: The document attachment to process
            user_id: User ID for storing the document
            conversation_id: Conversation ID for storing the document
            
        Returns:
            Dictionary with processing status, or None if failed
        """
        try:
            if not user_id or not conversation_id:
                logger.warning("Cannot process document: missing user_id or conversation_id")
                return None
            
            # Process and store document asynchronously in background
            success = document_processor.process_and_store_document(
                attachment_url=attachment.url,
                user_id=user_id,
                conversation_id=conversation_id,
                mime_type=attachment.mime_type,
            )
            
            if success:
                logger.info(f"Document {attachment.url} processed and stored successfully")
                return {
                    "type": "document",
                    "status": "stored",
                    "url": attachment.url,
                }
            else:
                raise ValueError(f"Failed to process document {attachment.url}")
                
        except Exception as e:
            logger.error(f"Error processing document attachment: {str(e)}")
            return None   
        
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
            if chunk.name.startswith("zoan_internal") or chunk.name == 'write_todos':
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
    
    def _extract_action_request(self, chunk, agent_name: str) -> List[ChunkContent]:
        """Extract action request from chunk's additional kwargs."""
        chunks = []
        if hasattr(chunk, 'value'):
            chunks.append(ChunkContent(
                type=ChunkType.ACTION_REQUEST,
                value=chunk.value["message"],
                agent=agent_name,
                index=0,
                metadata=chunk.value
            ))
            
        return chunks

    def _convert_chunk_content(self, chunk, agent_name: str) -> StreamingChunk:
        """Convert chunk content to the StreamingChunk model."""
        content_list = []
        
        # Extract tool outputs
        content_list.extend(self._extract_tool_outputs(chunk, agent_name))
        
        # Extract text content
        content_list.extend(self._extract_text_content(chunk, agent_name))
        
        return content_list
    
    def _convert_streaming_chunk(self, chunk, content_list: list, agent_name: str) -> StreamingChunk:       
        response_metadata = ResponseMetadata(
            status=chunk.response_metadata.get("status", "")
        )
        
        if len(content_list) == 0:
            content_list.append(ChunkContent(
                type=ChunkType.TEXT,
                value="",
                agent=agent_name,
                index=0,
                metadata={}
            ))
        
        return StreamingChunk(
            content=content_list,
            response_metadata=response_metadata
        )

    def _process_chunk(self, agent_name: str, chunk) -> StreamingChunk:
        """Process chunk content and extract annotations."""
        content_list = self._convert_chunk_content(chunk, agent_name)
        return self._convert_streaming_chunk(chunk, content_list, agent_name)
    
    def _graph_multimodal_input(
        self, 
        attachments: List[Attachment],
        user_id: str = "",
        conversation_id: str = ""
    ) -> List[HumanMessage]:
        """Create input configuration for the graph with image attachments."""
        mutimodal_input = []
        for attachment in attachments:
            if attachment.type == "file":
                content_blocks = [
                    {
                        "type": "text",
                        "text": "Attachment: {}".format(attachment.url)
                    }
                ]
                if attachment.mime_type in IMAGE_MIME_TYPES:
                    image_input = CompletionInput._process_image_attachment(attachment)
                    if image_input:
                        content_blocks.extend(image_input)
                elif attachment.mime_type in PDF_MIME_TYPES:
                    pdf_input = CompletionInput._process_pdf_attachment(attachment)
                    if pdf_input:
                        content_blocks.append(pdf_input)
                elif attachment.mime_type in AUDIO_MIME_TYPES:
                    audio_input = CompletionInput._process_audio_attachment(attachment)
                    if audio_input:
                        content_blocks.append(audio_input)
                elif attachment.mime_type in VIDEO_MIME_TYPES:
                    video_input = CompletionInput._process_video_attachment(attachment)
                    if video_input:
                        content_blocks.append(video_input)
                elif attachment.mime_type in DOCS_MIME_TYPES:
                    # Process and store document in Qdrant (doesn't add to multimodal input)
                    CompletionInput._process_doc_attachment(
                        attachment,
                        user_id=user_id,
                        conversation_id=conversation_id
                    )
                mutimodal_input.append(
                    HumanMessage(
                        content_blocks=content_blocks
                    )
                )
            elif attachment.type == "folder":
                mutimodal_input.append(
                    HumanMessage(
                        content_blocks=[
                            {
                                "type": "text",
                                "text": "Folder imported from Knowledge Hub: {}".format(attachment.url)
                            }
                        ]
                    )
                )
            
        return mutimodal_input

    def _create_graph_input(
        self, 
        message: str, 
        attachments: Optional[List[Attachment]] = None, 
        metadata: Metadata = Metadata(),
        user_id: str = "",
        conversation_id: str = ""
    ) -> Dict[str, Any]:
        """Create input configuration for the graph."""
        # User message
        messages = [
            HumanMessage(
                content_blocks=[
                    {
                        "type": "text",
                        "text": "[{datetime}] - {message}".format(datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message=message)
                    }
                ]
            )
        ]
        
        # Include attachments if available
        if attachments and len(attachments) > 0:
            mutimodal_input = self._graph_multimodal_input(
                attachments,
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            if len(mutimodal_input) > 0:
                messages.extend(mutimodal_input)
        
        # Include console logs if available
        if metadata.console_logs != "":
            messages.append(
                HumanMessage(
                    content_blocks=[
                        {
                            "type": "text",
                            "text": "Console Logs:\n{}".format(metadata.console_logs)
                        }
                    ]
                )
            )
            
        graph_input = {
            "messages": messages
        }
        
        return graph_input

    def _create_graph_config(
        self, 
        user_id: str,
        user_wallet_address: Optional[str],
        conversation_id: str, 
        auth_token: str = "",
        agent_kyas: Optional[Dict[str, Any]] = None,
        metadata: dict = {},
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
        config = {
            "configurable": {
                "user_id": user_id,
                "user_wallet_address": user_wallet_address,
                "thread_id": conversation_id,
                "auth_token": auth_token,
            },
            "callbacks": [self.langfuse_handler],
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
        }
        if agent_kyas:
            config["configurable"]["agent_kya"] = agent_kyas
        
        config["configurable"].update(metadata)
        agent_id = {
            _normalize_agent_name(agent.name): agent.id for agent in metadata.get("agent_mention_event").agent_configs
        }
        config["configurable"]["agent_id"] = agent_id
        
        return config
    
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


