"""Main application entry point."""

from contextlib import asynccontextmanager
import threading
import time

from dotenv import load_dotenv

# Load environment variables before other imports
load_dotenv()

from fastapi import FastAPI

from config.logging import setup_logging, get_logger
from handler.grpc.server import GRPCServerManager
from handler.router.setup import configure_app
from internal.database import init_db

# Setup logging
setup_logging()
logger = get_logger()

# Initialize gRPC server manager
grpc_manager = GRPCServerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    # Startup - Initialize database
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Database tables initialized")
    
    # Start gRPC server
    grpc_thread = threading.Thread(target=grpc_manager.run, daemon=True)
    grpc_thread.start()
    logger.info("Started gRPC server thread")
    
    # Give the server a moment to start
    time.sleep(1)
    
    yield
    
    # Shutdown
    grpc_manager.stop(grace=5.0)


# Create and configure FastAPI application
app = FastAPI(lifespan=lifespan)
configure_app(app)

