import asyncio
from contextlib import asynccontextmanager
from fastapi import Request, HTTPException, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from services.kafka_service import KafkaConsumer
from handler.consumer import message_consumer
from config.logging import get_logger

logger = get_logger()

class APIStatus:
    # Set the constant.
    NOT_FOUND = "NOT_FOUND"
    OK = "OK"
    ERROR = "ERROR"
    INVALID = "INVALID"

async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.detail.get("status", APIStatus.ERROR),
            "data": exc.detail.get("data", []),
            "message": exc.detail.get("message", "An error occurred.")
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_messages = [
        f"{error['loc'][-1]}: {error['msg']}" for error in errors
    ]
    message = "Invalid input: " + "; ".join(error_messages)

    return JSONResponse(
        status_code=400,
        content={
            "status": APIStatus.INVALID,
            "data": [],
            "message": message
        }
    )

@asynccontextmanager
async def kafka_lifespan(app: FastAPI):
    """Lifespan context manager for Kafka consumer"""
    loop = asyncio.get_running_loop()
    consumer_topics = list(message_consumer._handlers.keys())
    kafka_consumer = KafkaConsumer(
        asyncio_loop=loop,
        consumer_topics=consumer_topics
    )
    app.state.kafka = kafka_consumer

    kafka_consumer.start_consumer(message_consumer.on_message)

    yield   # <- App runs here

    # --- Shutdown ---
    if kafka_consumer:
        kafka_consumer.close()