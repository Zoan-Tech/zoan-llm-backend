import asyncio
from contextlib import asynccontextmanager
import logging
import os

from services.kafka_service import KafkaClient
# Configure application logging
def setup_logging():
    """Setup logging configuration for the application"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Set specific logger levels if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("minio").setLevel(logging.WARNING)

setup_logging()

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from uvicorn.config import LOGGING_CONFIG

from messaging.completion import on_message

from api import (
    health_check,
    completion
)

from api.utils import custom_http_exception_handler, validation_exception_handler

kafka: KafkaClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    kafka = KafkaClient(
        asyncio_loop=loop,
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=os.getenv("KAFKA_GROUP_ID"),
        topics=[os.getenv("KAFKA_TOPIC_REQUEST")],
    )
    app.state.kafka = kafka

    kafka.start_consumer(on_message)
    print("Kafka client started ✅")

    yield   # <- App runs here

    # --- Shutdown ---
    if kafka:
        kafka.close()
        print("Kafka client stopped 🛑")

app = FastAPI(lifespan=lifespan)

def configure_app(app: FastAPI):
    """Configure the FastAPI application with routes and exception handlers.
    """
    app.include_router(health_check.router, prefix="/api/v1", tags=["health_check"])
    app.include_router(completion.router, prefix="/api/v1", tags=["completion"])
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)

configure_app(app)  # Configure the app

# Set the access log level to WARNING to suppress request logs
LOGGING_CONFIG["loggers"]["uvicorn.access"]["level"] = "WARNING"
# Ensure only startup logs are shown by setting the main logger to INFO
LOGGING_CONFIG["loggers"]["uvicorn"]["level"] = "INFO"
