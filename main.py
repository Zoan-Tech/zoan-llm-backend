"""Main application entry point."""

from contextlib import asynccontextmanager
import threading
import time
import asyncio

from dotenv import load_dotenv

# Load environment variables before other imports
load_dotenv()

from fastapi import FastAPI

from config.logging import setup_logging, get_logger
from handler.grpc.server import GRPCServerManager
from handler.router.setup import configure_app
from handler.kafka import KafkaHandlerManager
from handler.worker import WorkerManager
from internal.database import init_db

# Setup logging
setup_logging()
logger = get_logger()

# Initialize gRPC server manager
grpc_manager = GRPCServerManager()

# Global Kafka handler manager
kafka_manager = None
kafka_thread = None

# Global worker manager
worker_manager = None
worker_thread = None


def start_workers():
    """Start all workers in a separate thread with asyncio event loop."""
    global worker_manager
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        worker_manager = WorkerManager(asyncio_loop=loop)
        
        # Start all registered workers
        loop.run_until_complete(worker_manager.start_all())
        
    except Exception as e:
        logger.error(f"Error in worker thread: {str(e)}")
    finally:
        loop.close()


def start_kafka_consumers():
    """Start Kafka consumers in a separate thread with asyncio event loop."""
    global kafka_manager
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        kafka_manager = KafkaHandlerManager(asyncio_loop=loop)
        
        # Discover and initialize consumers
        consumers = kafka_manager.initialize_consumers()
        
        if not consumers:
            logger.warning("No Kafka consumers initialized")
            return
        
        # Start all consumers
        kafka_manager.start_all_consumers()
        logger.info("Kafka consumers started: " + str(kafka_manager.topics))
        
        # Keep the loop running
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"Error in Kafka consumer thread: {str(e)}")
    finally:
        if kafka_manager:
            kafka_manager.close_all_consumers()
        loop.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    global kafka_thread, worker_thread
    
    # Startup - Initialize database
    init_db()
    logger.info("Database tables initialized")
    
    # Start gRPC server
    grpc_thread = threading.Thread(target=grpc_manager.run, daemon=True)
    grpc_thread.start()
    logger.info("Started gRPC server thread")
    
    # Start all workers
    worker_thread = threading.Thread(target=start_workers, daemon=True)
    worker_thread.start()
    
    # Start Kafka consumers
    kafka_thread = threading.Thread(target=start_kafka_consumers, daemon=True)
    kafka_thread.start()
    
    # Give the servers a moment to start
    time.sleep(1)
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")
    
    # Stop gRPC server
    grpc_manager.stop(grace=5.0)
    
    # Stop all workers
    if worker_manager:
        worker_manager.stop_all()
    
    # Stop Kafka consumers
    if kafka_manager:
        kafka_manager.stop_all_consumers()
    
    logger.info("Services shutdown complete")


# Create and configure FastAPI application
app = FastAPI(lifespan=lifespan)
configure_app(app)


