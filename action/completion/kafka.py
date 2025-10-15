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
from services.connector.kafka_service import KafkaProducer
from config import Config
from action.completion.base import BaseCompletionAction, StreamingStatus, PRIMARY_AGENT

logger = get_logger()

# Processing Configuration
KAFKA_FLUSH_TIMEOUT = 0.1


class KafkaCompletionAction(BaseCompletionAction):
    """
    Kafka-based completion action.
    
    Sends streaming chunks via Kafka producer to a configured topic.
    Uses `create_completion()` method to send chunks to Kafka topic.
    """
    
    def __init__(self):
        """Initialize the KafkaCompletionAction with Kafka producer."""
        super().__init__()
        self.kafka_topic_response = Config.KAFKA_TOPIC_RESPONSE
        self.kafka_producer = KafkaProducer()

    def _send_error_message(self, conversation_id: str, error_message: str):
        """Send error message to Kafka topic."""
        error_chunk = self._create_error_chunk(error_message)
        self.kafka_producer.produce(
            topic=self.kafka_topic_response,
            key=conversation_id,
            value=error_chunk.model_dump(),
        )

    def _send_streaming_chunk(self, conversation_id: str, streaming_chunk: StreamingChunk) -> None:
        """Send streaming chunk to Kafka topic."""
        self.kafka_producer.produce(
            topic=self.kafka_topic_response,
            key=conversation_id,
            value=streaming_chunk.model_dump()
        )

    async def _process_graph_stream(
        self, 
        compiled_graph: CompiledStateGraph, 
        input_data: Dict[str, Any], 
        config: Dict[str, Any], 
        conversation_id: str
    ) -> tuple[Optional[StreamingChunk], Dict[str, Any]]:
        """Process the graph stream and send chunks to Kafka."""
        annotation = {}
        annotation["app"] = {}
        last_chunk = None
        
        for agent, chunk in compiled_graph.stream(input_data, config=config, stream_mode="messages", subgraphs=True):                    
            agent_name = self._extract_agent_name(agent)
                
            streaming_chunk = self._process_chunk(agent_name, chunk[0], annotation)
            self._send_streaming_chunk(conversation_id, streaming_chunk)
            last_chunk = streaming_chunk
            
        return last_chunk, annotation

    async def _build_game_files(self, container_id: str, conversation_id: str, annotation: dict, config: dict) -> None:
        """Build game files and send to Kafka."""
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
            
            self._send_streaming_chunk(conversation_id, game_built_object)
            logger.debug("Sending game built object", game_built_object.model_dump())
            
        except Exception as e:
            logger.error(f"Failed to build game files for container {container_id}: {str(e)}")

    def _send_final_chunk(self, last_chunk: StreamingChunk, conversation_id: str) -> None:
        """Send final completion chunk to Kafka."""
        final_chunk = self._create_final_chunk(last_chunk)
        if final_chunk:
            self._send_streaming_chunk(conversation_id, final_chunk)

    @observe(as_type="generation")
    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        agents: List[AgentConfig],
        attachments: Optional[List[Attachment]] = None,
        metadata: Metadata = Metadata(),
    ) -> None:
        """
        Create a completion using Kafka streaming.
        
        Processes the graph and sends all chunks to the configured Kafka topic.
        
        Args:
            user_id: ID of the user
            conversation_id: ID of the conversation
            message: User's message
            agents: List of agent configurations
            attachments: Optional list of attachments
            metadata: Additional metadata
        """
        compiled_graph = self.graph_builder.get_compiled_graph(agents)
        input_data = self._create_graph_input(message, attachments, metadata)
        config = self._create_graph_config(user_id, conversation_id)
        
        try:
            last_chunk, annotation = await self._process_graph_stream(
                compiled_graph, input_data, config, conversation_id
            )
            
            logger.info("Sent completion response: %s", conversation_id)
            
            # Build game files if container ID is available
            if annotation["app"].get("latest"):
                container_id = annotation["app"]["latest"]["container_id"]
                await self._build_game_files(container_id, conversation_id, annotation, config)
            
            # Send final completion chunk
            self._send_final_chunk(last_chunk, conversation_id)
                
        except Exception as e:
            logger.error(f"Error during graph streaming: {str(e)}")
            self._send_error_message(conversation_id, str(e))


kafka_completion_action = KafkaCompletionAction()
