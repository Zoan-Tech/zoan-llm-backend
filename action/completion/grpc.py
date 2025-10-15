import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from langgraph.graph.state import CompiledStateGraph
from langfuse import observe

from config.logging import get_logger
from model import (
    AgentConfig,
    StreamingChunk,
    ChunkContent,
    ResponseMetadata,
    Attachment,
    Metadata,
)
from action.chat_title_generator import chat_title_generator
from action.completion.base import BaseCompletionAction, StreamingStatus, PRIMARY_AGENT

logger = get_logger()


class GrpcCompletionAction(BaseCompletionAction):
    """
    gRPC-based completion action.
    
    Yields streaming chunks directly as AsyncGenerator for gRPC streaming.
    Uses `create_completion_stream()` method to yield chunks.
    """
    
    def __init__(self):
        """Initialize the GrpcCompletionAction."""
        super().__init__()

    async def _start_title_generation_background(
        self,
        user_message: str,
        messages: List,
        conversation_id: str,
        auth_token: str
    ) -> None:
        """
        Start title generation as a background task (fire and forget).
        
        Args:
            user_message: The user's message
            messages: Conversation history messages
            conversation_id: ID of the conversation
            auth_token: Authorization token for webhook
        """
        async def run_title_generation():
            try:
                await chat_title_generator.generate_and_update_title(
                    user_message,
                    messages, 
                    conversation_id,
                    auth_token=auth_token
                )
            except Exception as e:
                logger.warning(f"[GrpcCompletionAction] Title generation failed: {str(e)}")
        
        # Create task without awaiting (fire and forget)
        asyncio.create_task(run_title_generation())

    async def _stream_graph_chunks(
        self,
        compiled_graph: CompiledStateGraph,
        input_data: Dict[str, Any],
        config: Dict[str, Any],
        annotation: Dict[str, Any]
    ) -> AsyncGenerator[tuple[StreamingChunk, Optional[StreamingChunk]], None]:
        """
        Stream chunks from the graph execution.
        
        Args:
            compiled_graph: Compiled LangGraph state graph
            input_data: Input data for the graph
            config: Graph configuration
            annotation: Dictionary to store annotations
            
        Yields:
            Tuple of (streaming_chunk, last_chunk)
        """
        last_chunk = None
        
        for agent, chunk in compiled_graph.stream(
            input_data, 
            config=config, 
            stream_mode="messages", 
            subgraphs=True
        ):
            agent_name = self._extract_agent_name(agent)
            streaming_chunk = self._process_chunk(agent_name, chunk[0], annotation)
            last_chunk = streaming_chunk
            yield streaming_chunk, last_chunk

    async def _build_game_files(self, container_id: str, conversation_id: str, annotation: dict, config: dict) -> AsyncGenerator[StreamingChunk, None]:
        """Build game files and yield game signal chunk."""
        try:
            logger.info(f"Building game files for container {container_id} in conversation {conversation_id}")
            await self._extract_app_versions(annotation, config)
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
                response_metadata=ResponseMetadata(status=StreamingStatus.COMPLETED)
            )
            
            logger.debug("Sending game built object", game_built_object.model_dump())
            yield game_built_object
            
        except Exception as e:
            logger.error(f"Failed to build game files for container {container_id}: {str(e)}")

    @observe(as_type="generation")
    async def create_completion_stream(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: List[AgentConfig],
        attachments: Optional[List[Attachment]] = None,
        metadata: Metadata = Metadata(),
        auth_token: str = "",
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Create a completion and stream responses directly (for gRPC).
        
        This method orchestrates the entire completion flow:
        1. Starts background title generation (if applicable)
        2. Streams graph processing chunks
        3. Builds and streams game files (if applicable)
        4. Yields final completion chunk
        
        Args:
            user_id: ID of the user
            conversation_id: ID of the conversation
            message: User's message
            agents: List of agent configurations
            attachments: Optional list of attachments
            metadata: Additional metadata
            auth_token: Authorization token for webhook calls
            
        Yields:
            StreamingChunk objects containing completion responses
        """
        # Acquire conversation lock to prevent concurrent processing
        conversation_lock = self._conversation_locks[conversation_id]
        
        # Try to acquire lock without blocking
        lock_acquired = conversation_lock.acquire(blocking=False)
        if not lock_acquired:
            logger.warning(f"[GrpcCompletionAction] Conversation {conversation_id} is already being processed")
            yield StreamingChunk(
                content=[],
                response_metadata=ResponseMetadata(
                    status="error: Conversation is already being processed by another request"
                )
            )
            return
        
        try:
            logger.info(f"Starting completion stream for conversation {conversation_id}")
            # Initialize graph components
            compiled_graph = self.graph_builder.get_compiled_graph(agents)
            input_data = self._create_graph_input(message, attachments, metadata)
            config = self._create_graph_config(user_id, conversation_id)
            
            # Start title generation in background (fire and forget)
            try:
                messages = await self._get_conversation_messages(config)
                await self._start_title_generation_background(message, messages, conversation_id, auth_token)
            except Exception as e:
                logger.warning(f"[GrpcCompletionAction] Failed to start title generation: {str(e)}")
            
            # Main streaming flow
            try:
                annotation = {"app": {}}
                last_chunk = None
                
                # Stream graph processing chunks
                async for streaming_chunk, last_chunk in self._stream_graph_chunks(
                    compiled_graph, 
                    input_data, 
                    config, 
                    annotation
                ):
                    yield streaming_chunk
                
                # Build and stream game files if available
                if annotation["app"].get("latest"):
                    container_id = annotation["app"]["latest"]["container_id"]
                    async for game_chunk in self._build_game_files(
                        container_id, 
                        conversation_id, 
                        annotation, 
                        config
                    ):
                        yield game_chunk
                
                # Send final completion chunk
                if last_chunk:
                    yield self._create_final_chunk(last_chunk)
                    
            except Exception as e:
                logger.error(f"[GrpcCompletionAction] Error during graph streaming: {str(e)}")
                yield self._create_error_chunk(str(e))
        
        finally:
            # Always release the lock
            conversation_lock.release()
            
            # Cleanup lock if no longer needed (optional, prevents memory leak)
            with self._locks_cleanup_lock:
                if conversation_id in self._conversation_locks:
                    # Only delete if lock is not held by anyone
                    if not self._conversation_locks[conversation_id].locked():
                        del self._conversation_locks[conversation_id]


grpc_completion_action = GrpcCompletionAction()
