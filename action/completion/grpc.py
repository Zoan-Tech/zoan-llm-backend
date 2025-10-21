import asyncio
import json
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

    async def _stream_graph_chunks(
        self,
        compiled_graph: CompiledStateGraph,
        input_data: Dict[str, Any],
        config: Dict[str, Any],
        code_interpreter_call: list
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
            streaming_chunk = self._process_chunk(agent_name, chunk[0], code_interpreter_call)
            last_chunk = streaming_chunk
            yield streaming_chunk, last_chunk

    async def _build_game_files(self, conversation_id: str, code_interpreter_call: list) -> AsyncGenerator[StreamingChunk, None]:
        """Build game files and yield game signal chunk."""
        try:
            if len(code_interpreter_call) == 0:
                return
            
            container_id = code_interpreter_call[0].get("container_id", "")
            minio_prefix = await self.minio_builder.build_openai_game_file(
                container_id, 
                thread_id=conversation_id,
                code_interpreter_call=code_interpreter_call   
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
            
            logger.debug(f"Sending game built object {game_built_object.model_dump()}")
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
        1. Streams graph processing chunks
        2. Builds and streams game files (if applicable)
        3. Yields final completion chunk
        
        Note: Title generation is now handled by the Primary Agent as a tool,
        not as a background task in the completion flow.
        
        Args:
            user_id: ID of the user
            conversation_id: ID of the conversation
            message: User's message
            agents: List of agent configurations
            attachments: Optional list of attachments
            metadata: Additional metadata
            auth_token: Authorization token (passed to agents via config)
            
        Yields:
            StreamingChunk objects containing completion responses
        """
        # Acquire conversation lock to prevent concurrent processing
        conversation_lock = self._conversation_locks[conversation_id]
        
        # Try to acquire lock without blocking
        lock_acquired = conversation_lock.acquire(blocking=False)
        if not lock_acquired:
            logger.warning(f"[GrpcCompletionAction] Conversation {conversation_id} is already being processed")
            yield self._create_error_chunk(str(e))
            return
        
        try:
            logger.info(f"Starting completion stream for conversation {conversation_id}")
            # Initialize graph components
            compiled_graph = self.graph_builder.get_compiled_graph(agents)
            input_data = self._create_graph_input(message, attachments, metadata)
            config = self._create_graph_config(user_id, conversation_id, auth_token)
            
            # Main streaming flow
            try:
                code_interpreter_call = []
                last_chunk = None
                
                # Stream graph processing chunks
                try:
                    async for streaming_chunk, last_chunk in self._stream_graph_chunks(
                        compiled_graph, 
                        input_data, 
                        config, 
                        code_interpreter_call
                    ):
                        yield streaming_chunk
                except Exception as graph_error:
                    logger.error(f"[GrpcCompletionAction] Error during graph chunk streaming: {str(graph_error)}", exc_info=True)
                    raise  # Re-raise to be caught by outer exception handler
                
                # Build and stream game files if available
                async for game_chunk in self._build_game_files(
                    conversation_id, 
                    code_interpreter_call, 
                ):
                    yield game_chunk
                
                # Send final completion chunk
                if last_chunk:
                    yield self._create_final_chunk(last_chunk)
                    
            except Exception as e:
                logger.error(f"[GrpcCompletionAction] Error during graph streaming: {str(e)}", exc_info=True)
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
