import asyncio

from grpc_generated.completion import completion_pb2_grpc, completion_pb2
from config.logging import get_logger, setup_logging
from model.completion import CompletionRequest
from action.completion import grpc_completion_action

setup_logging()
logger = get_logger()

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
                attachments=[
                    {
                        "url": att.url,
                        "mime_type": att.mime_type
                    } for att in request.attachments
                ] if request.attachments else [],
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
                    "console_logs": request.metadata.console_logs
                }
            )
            
            logger.debug(f"Received completion request: {completion_object.model_dump()}")
            
            # Process completion and stream responses using asyncio.run
            async def async_generator():
                async for chunk in grpc_completion_action.create_completion_stream(
                    user_id=completion_object.user_id,
                    conversation_id=completion_object.conversation_id,
                    message=completion_object.message,
                    agents=completion_object.agents,
                    attachments=completion_object.attachments,
                    metadata=completion_object.metadata,
                    auth_token=auth_token,
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
                        
                        # Convert our model to protobuf response
                        chunk_content = [
                            completion_pb2.ChunkContent(
                                type=content.type,
                                text=content.text,
                                agent=content.agent,
                                index=content.index,
                                url=content.url,
                                game_version=content.game_version or ""
                            ) for content in chunk.content
                        ]
                        
                        response_metadata = completion_pb2.ResponseMetadata(
                            status=chunk.response_metadata.status
                        )
                        
                        streaming_chunk = completion_pb2.StreamingChunk(
                            content=chunk_content,
                            response_metadata=response_metadata
                        )
                        
                        yield streaming_chunk
                    except StopAsyncIteration:
                        break
                    except Exception as e:
                        yield grpc_completion_action._create_error_chunk(str(e))
                        break
            finally:
                logger.info(f"Finishing loop completion gRPC for chat {request.conversation_id}")
                loop.close()
                
        except Exception as e:
            logger.error(f"Error handling completion message: {str(e)} for chat {request.conversation_id}")
            yield grpc_completion_action._create_error_chunk(str(e))