"""FastAPI application configuration and setup."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from handler.router import (
    health_check,
    media,
    vectorizer,
)
from handler.utils import custom_http_exception_handler, validation_exception_handler


def configure_routes(app: FastAPI) -> None:
    """Configure application routes."""
    app.include_router(health_check.router, prefix="/api/v1", tags=["health_check"])
    app.include_router(media.description.router, prefix="/api/v1", tags=["media_description"])
    app.include_router(vectorizer.router, prefix="/api/v1", tags=["vectorizer"])


def configure_exception_handlers(app: FastAPI) -> None:
    """Configure application exception handlers."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)


def configure_app(app: FastAPI) -> None:
    """Configure the FastAPI application with routes and exception handlers."""
    configure_routes(app)
    configure_exception_handlers(app)
