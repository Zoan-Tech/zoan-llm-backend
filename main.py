from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
import threading
import time
import asyncio

from config.logging import setup_logging, get_logger
import grpc
from concurrent import futures
from handler.grpc.completion import CompletionServiceServicer
from grpc_generated.completion import completion_pb2_grpc

from handler.consumer import message_consumer
from services.connector.kafka_service import KafkaConsumer

setup_logging()

logger = get_logger()

from config import Config
from handler.router import (
    health_check,
)

# Global gRPC server and Kafka consumer
grpc_server = None
grpc_thread = None
kafka_consumer = None

def start_grpc_server():
    """Start the gRPC server in a separate thread."""
    global grpc_server
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS))
    completion_pb2_grpc.add_CompletionServiceServicer_to_server( # type: ignore
        CompletionServiceServicer(), grpc_server
    )
    
    # Start gRPC server
    listen_addr = f'[::]:{Config.GRPC_PORT}'
    grpc_server.add_insecure_port(listen_addr)
    grpc_server.start()
    logger.info(f"gRPC server started on {listen_addr}")
    
    # Keep the server running
    try:
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC server shutdown requested")

def start_kafka_consumer():
    """Start the Kafka consumer in the asyncio event loop."""
    global kafka_consumer
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        consumer_topics = list(message_consumer._handlers.keys())
        logger.info(f"Starting Kafka consumer for topics: {consumer_topics}")
        
        kafka_consumer = KafkaConsumer(
            asyncio_loop=loop,
            consumer_topics=consumer_topics,
        )
        
        kafka_consumer.start_consumer(message_consumer.on_message)
        
        # Keep the loop running
        loop.run_forever()
    except Exception as e:
        logger.error(f"Error starting Kafka consumer: {str(e)}")
    finally:
        loop.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global grpc_thread
    
    # Start gRPC server
    grpc_thread = threading.Thread(target=start_grpc_server, daemon=True)
    grpc_thread.start()
    logger.info("Started gRPC server thread")
    
    # Start Kafka consumer
    kafka_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    kafka_thread.start()
    logger.info("Started Kafka consumer thread")
    
    # Give the servers a moment to start
    time.sleep(1)
    
    yield
    
    # Shutdown
    if grpc_server:
        grpc_server.stop(grace=5.0)
        logger.info("gRPC server stopped")
    
    if kafka_consumer:
        kafka_consumer.close()
        logger.info("Kafka consumer stopped")

from handler.utils import custom_http_exception_handler, validation_exception_handler

app = FastAPI(lifespan=lifespan)

def configure_app(app: FastAPI):
    """Configure the FastAPI application with routes and exception handlers.
    """
    app.include_router(health_check.router, prefix="/api/v1", tags=["health_check"])
    # app.include_router(completion.router, prefix="/api/v1", tags=["completion"])
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)

configure_app(app)  # Configure the app
