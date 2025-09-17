from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from config.logging import setup_logging, get_logger
setup_logging()

logger = get_logger()

from api import (
    health_check,
    completion
)

from api.utils import custom_http_exception_handler, validation_exception_handler, kafka_lifespan

app = FastAPI(lifespan=kafka_lifespan)

def configure_app(app: FastAPI):
    """Configure the FastAPI application with routes and exception handlers.
    """
    app.include_router(health_check.router, prefix="/api/v1", tags=["health_check"])
    app.include_router(completion.router, prefix="/api/v1", tags=["completion"])
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)

configure_app(app)  # Configure the app
