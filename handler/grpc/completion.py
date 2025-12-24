import asyncio

from handler.grpc.grpc_generated.completion import completion_pb2_grpc, completion_pb2
from config.logging import get_logger, setup_logging
from model.completion import CompletionRequest
from action.completion import grpc_completion_action

setup_logging()
logger = get_logger()

def _convert_to_protobuf(pydantic_chunk):
    """Convert Pydantic StreamingChunk to Protobuf StreamingChunk."""
    chunk_content = [
        completion_pb2.ChunkContent(
            type=content.type,
            value=content.value,
            agent=content.agent,
            index=content.index,
            metadata={k: str(v) for k, v in content.metadata.items()}
        ) for content in pydantic_chunk.content
    ]
    
    response_metadata = completion_pb2.ResponseMetadata(
        status=pydantic_chunk.response_metadata.status
    )
    
    return completion_pb2.StreamingChunk(
        content=chunk_content,
        response_metadata=response_metadata
    )

class CompletionServiceServicer(completion_pb2_grpc.CompletionServiceServicer):
    def Completion(self, request, context): # type: ignore
        """Handle completion requests and stream responses."""
        try:
            metadata = dict(context.invocation_metadata())
            # Get authorization token
            auth_token = metadata.get('authorization', '')
            # Convert protobuf request to our model
            completion_object = CompletionRequest(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                message=request.message,
                agents=[
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "model": agent.model,
                        "model_kwargs": {
                            "temperature": agent.model_kwargs.temperature if agent.model_kwargs.HasField('temperature') else None,
                            "max_tokens": agent.model_kwargs.max_tokens if agent.model_kwargs.HasField('max_tokens') else None,
                            "top_p": agent.model_kwargs.top_p if agent.model_kwargs.HasField('top_p') else None,
                            "stop": list(agent.model_kwargs.stop) if agent.model_kwargs.stop else []
                        },
                        "description": agent.description if agent.HasField('description') else None,
                        "instruction": agent.instruction if agent.HasField('instruction') else None,
                        "system_prompt": agent.system_prompt if agent.HasField('system_prompt') else None,
                        "is_enabled": agent.is_enabled,
                        "is_primary": agent.is_primary,
                        "workflows": [
                            {
                                "id": workflow.id if workflow.HasField('id') else None,
                                "name": workflow.name,
                                "description": workflow.description if workflow.HasField('description') else None,
                                "steps": [
                                    {
                                        "name": step.name,
                                        "type": step.type,
                                        "description": step.description if step.HasField('description') else None,
                                        "args": {
                                            key: {
                                                "type": arg.type,
                                                "description": arg.description if arg.HasField('description') else None,
                                                "value": arg.value if arg.HasField('value') else None,
                                                "required": arg.required,
                                                "end_user_input": arg.end_user_input
                                            } for key, arg in step.args.items()
                                        },
                                        "response_mapping": dict(step.response_mapping)
                                    } for step in workflow.steps
                                ]
                            } for workflow in agent.workflows
                        ],
                        "stream_usage": agent.stream_usage
                    } for agent in request.agents
                ],
                metadata={
                    "console_logs": request.metadata.console_logs,
                    "attachments": [
                        {
                            "url": att.url,
                            "file_name": att.file_name,
                            "mime_type": att.mime_type,
                            "file_size": att.file_size,
                            "type": att.type
                        } for att in request.metadata.attachments
                    ] if request.metadata.attachments else [],
                    "web_search": request.metadata.web_search
                }
            )
            
            logger.debug(f"Received completion request: {completion_object.model_dump()}")
            async def async_generator():
                async for chunk in grpc_completion_action.create_completion_stream(
                    user_id=completion_object.user_id,
                    conversation_id=completion_object.conversation_id,
                    message=completion_object.message,
                    agents=completion_object.agents,
                    attachments=completion_object.metadata.attachments,
                    metadata=completion_object.metadata,
                    auth_token=auth_token,
                    web_search=completion_object.metadata.web_search,
                ):
                    yield chunk
            
            # Convert async generator to sync generator
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async_gen = async_generator()
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        
                        # Convert Pydantic model to protobuf response
                        streaming_chunk = _convert_to_protobuf(chunk)
                        
                        yield streaming_chunk
                    except StopAsyncIteration:
                        break
                    except Exception as inner_error:
                        logger.error(f"Error processing chunk: {str(inner_error)}", exc_info=True)
                        # Reuse base.py method and convert to protobuf
                        error_chunk = grpc_completion_action._create_error_chunk(str(inner_error))
                        yield _convert_to_protobuf(error_chunk)
                        break
            finally:
                logger.info(f"Finishing loop completion gRPC for chat {request.conversation_id}.")
                loop.close()
                
        except Exception as outer_error:
            logger.error(f"Error handling completion message: {str(outer_error)} for chat {request.conversation_id}")
            # Reuse base.py method and convert to protobuf
            error_chunk = grpc_completion_action._create_error_chunk(str(outer_error))
            yield _convert_to_protobuf(error_chunk)