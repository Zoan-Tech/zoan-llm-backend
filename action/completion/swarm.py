import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from config.logging import get_logger
from model.completion import (
    AgentConfig,
    StreamingChunk,
    Attachment,
    Metadata,
    ResponseMetadata,
)
from model.graph import (
    Action,
    ActionMetadata,
)
from action.completion.base import BaseCompletionAction

logger = get_logger()

class SwarmCompletion(BaseCompletionAction):
    """
    Completion action that supports interruption and resumption via user decisions with swarm multi-agent architecture.
    """
    
    def __init__(self):
        """Initialize the SwarmCompletion."""
        super().__init__()
        # Store pending decisions per thread and action_name
        # Structure: {thread_id: {action_name: future}}
        self.pending_decisions: Dict[str, Dict[str, asyncio.Future]] = {}

    async def _stream_graph_chunks(
        self,
        compiled_graph: CompiledStateGraph,
        input_data: Dict[str, Any],
        config: Dict[str, Any],
        thread_id: str
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
        current_input = input_data

        
        while True:
            interrupted = False

            for agent, mode, chunk in compiled_graph.stream(
                current_input, 
                config=config, 
                stream_mode=['messages', 'updates'],  
                subgraphs=True,
            ):  
                agent_name = self._extract_agent_name(agent)
                if mode == "messages":
                    token, _ = chunk
                    streaming_chunk = self._process_chunk(agent_name, token)
                    yield streaming_chunk
                elif mode == "updates":
                    if "__interrupt__" in chunk:
                        content_list = self._extract_action_request(chunk['__interrupt__'][0], agent_name)
                        action_name = chunk['__interrupt__'][0].value.get("action_name", "unknown_action")
                        
                        # Create and register the future BEFORE yielding to avoid race condition
                        future = asyncio.Future()
                        if thread_id not in self.pending_decisions:
                            self.pending_decisions[thread_id] = {}
                        self.pending_decisions[thread_id][action_name] = future
                        
                        # Now yield the interrupt chunk
                        yield StreamingChunk(
                            content=content_list,
                            response_metadata=ResponseMetadata(status="interrupt")
                        )
            
                        # Wait for the decision on the pre-created future
                        decision = await self._wait_for_decision(thread_id, action_name, future)
                        
                        current_input = decision
                        interrupted = True
                        
                        break  # Exit for loop to restart streaming

            if not interrupted:
                break  # Exit outer while loop if not interrupted                 
            
    async def _wait_for_decision(
        self, 
        thread_id: str,
        action_name: str,
        future: asyncio.Future,
        timeout: int = 10  # 1 minute timeout
    ) -> Dict[str, Any]:
        """Wait for user decision with timeout."""
        try:
            # Wait for decision with timeout
            decision = await asyncio.wait_for(future, timeout=timeout)
            return decision
        except asyncio.TimeoutError:
            logger.warning(f"[WAIT] TIMEOUT after {timeout}s for thread_id={thread_id}, action_name={action_name}")
            # Auto-reject on timeout
            return Command(resume={
                "action": Action.REJECTED.value
            })
        finally:
            # Clean up after a short delay to allow any late submissions to be caught
            await asyncio.sleep(0.1)
            if thread_id in self.pending_decisions:
                self.pending_decisions[thread_id].pop(action_name, None)
                # Remove thread entry if no more pending actions
                if not self.pending_decisions[thread_id]:
                    self.pending_decisions.pop(thread_id, None)
            
    async def submit_decision(
        self,
        thread_id: str,
        action_name: str,
        decision: Action,
        metadata: Optional[ActionMetadata] = None
    ) -> bool:
        """Submit user's decision to resume the waiting stream."""
        decision_data = {
            "action": decision.value
        }
        if metadata:
            decision_data.update(metadata.model_dump(exclude_unset=True))
        
        decision_data = Command(resume=decision_data)
        
        # Get the future for this specific thread and action
        thread_decisions = self.pending_decisions.get(thread_id, {})
        
        # If action_name is empty or not found, try to get the first available pending action
        if not action_name or action_name not in thread_decisions:
            if thread_decisions:
                # Get the first (and likely only) pending action
                action_name = next(iter(thread_decisions.keys()))
        
        future = thread_decisions.get(action_name)
        
        if future and not future.done():
            future.set_result(decision_data)
            return True
        
        logger.warning(f"[SUBMIT] FAILED - No valid future found or future already done for thread_id={thread_id}, action_name={action_name}")
        return False

    async def create_graph_completion_stream(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: List[AgentConfig],
        attachments: Optional[List[Attachment]] = None,
        metadata: Metadata = Metadata(),
        auth_token: str = "",
        web_search: bool = False,
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
        agent_kyas = {
            agent.name: agent.decrypt_fields() for agent in agents if agent.agent_kya
        }
        
        # Try to acquire lock without blocking
        lock_acquired = conversation_lock.acquire(blocking=False)
        if not lock_acquired:
            logger.warning(f"[SwarmCompletion] Conversation {conversation_id} is already being processed")
            yield self._create_error_chunk("Conversation is already being processed")
            return
        
        try:
            logger.info(f"Starting completion stream for conversation {conversation_id}")
            # Initialize graph components
            compiled_graph = self.graph_builder.get_compiled_graph(agents, web_search=web_search)
            
            input_data = self._create_graph_input(
                message, 
                attachments, 
                metadata,
                user_id=user_id,
                conversation_id=conversation_id
            )
            config = self._create_graph_config(user_id, conversation_id, auth_token, agent_kyas)
            
            # Main streaming flow
            try:
                
                # Stream graph processing chunks
                try:
                    async for streaming_chunk in self._stream_graph_chunks(
                        compiled_graph, 
                        input_data, 
                        config, 
                        thread_id=conversation_id
                    ):
                        yield streaming_chunk
                except Exception as graph_error:
                    logger.error(f"[SwarmCompletion] Error during graph chunk streaming: {str(graph_error)}", exc_info=True)
                    raise  # Re-raise to be caught by outer exception handler
                
                # Send final completion chunk
                final_chunk = self._create_final_chunk()
                logger.debug(f"[SwarmCompletion] Final chunk: {final_chunk}")
                yield final_chunk
                    
            except Exception as e:
                logger.error(f"[SwarmCompletion] Error during graph streaming: {str(e)}", exc_info=True)
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
                        
    

    async def create_agent_completion(
        self,
        user_id: str,
        user_wallet_id: Optional[str],
        user_wallet_address: Optional[str],
        conversation_id: str,
        message: str,
        agent_config: AgentConfig,
        attachments: Optional[List[Attachment]] = None,
        metadata: dict = {},
    ) -> list:
        """
        Create a completion for a single agent (non-streaming).
        """
        agent_kyas = {
            agent_config.name: agent_config.decrypt_fields()
        }
        
        agent = self.graph_builder.get_agent(
            agent_config, 
        )
        
        input_data = self._create_graph_input(
            message, 
            attachments, 
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        config = self._create_graph_config(
            user_id,
            user_wallet_id,
            user_wallet_address,
            conversation_id,
            agent_kyas=agent_kyas,
            metadata=metadata
        )
        
        result = agent.invoke(
            input=input_data,
            config=config,
        )
        
        reply_content = result['messages'][-1].content
        
        return reply_content
        
swarm_completion = SwarmCompletion()
