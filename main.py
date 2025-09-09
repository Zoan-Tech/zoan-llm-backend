from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from uvicorn.config import LOGGING_CONFIG

from config.logging import setup_logging
setup_logging()

from api import (
    health_check,
    completion
)

from api.utils import custom_http_exception_handler, validation_exception_handler

app = FastAPI()

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
