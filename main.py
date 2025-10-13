from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
import threading
import time

from config.logging import setup_logging, get_logger
import grpc
from concurrent import futures
from handler.grpc.completion import CompletionServiceServicer
from grpc_generated.completion import completion_pb2_grpc

setup_logging()

logger = get_logger()

from api import (
    health_check,
    # completion
)

# Global gRPC server
grpc_server = None
grpc_thread = None

def start_grpc_server():
    """Start the gRPC server in a separate thread."""
    global grpc_server
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    completion_pb2_grpc.add_CompletionServiceServicer_to_server( # type: ignore
        CompletionServiceServicer(), grpc_server
    )
    
    # Start gRPC server
    listen_addr = '[::]:50051'
    grpc_server.add_insecure_port(listen_addr)
    grpc_server.start()
    logger.info(f"gRPC server started on {listen_addr}")
    
    # Keep the server running
    try:
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC server shutdown requested")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global grpc_thread
    grpc_thread = threading.Thread(target=start_grpc_server, daemon=True)
    grpc_thread.start()
    
    # Give the server a moment to start
    time.sleep(1)
    
    # Start Kafka consumer
    # await kafka_lifespan(app)
    
    yield
    
    # Shutdown
    if grpc_server:
        grpc_server.stop(grace=5.0)
    logger.info("gRPC server stopped")

from api.utils import custom_http_exception_handler, validation_exception_handler

app = FastAPI(lifespan=lifespan)

def configure_app(app: FastAPI):
    """Configure the FastAPI application with routes and exception handlers.
    """
    app.include_router(health_check.router, prefix="/api/v1", tags=["health_check"])
    # app.include_router(completion.router, prefix="/api/v1", tags=["completion"])
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)

configure_app(app)  # Configure the app
