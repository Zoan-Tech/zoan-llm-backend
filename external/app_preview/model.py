from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from external.app_preview.enums import BuildStatus

T = TypeVar("T")

# ============================================================================
# Base Response Models
# ============================================================================

class AppPreviewResponse(BaseModel, Generic[T]):
    """Generic response model for app preview API endpoints."""
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["OK", "NOT_FOUND", "ERROR", "INVALID"] = Field(
        ...,
        description="Overall result"
    )
    data: T | list[T] | None = Field(
        None,
        description="Payload for the response; may be a single item, a list, or null"
    )
    message: str = Field(..., description="More details about the request outcome")
    error: dict[str, Any] | None = Field(None, description="Error details if any")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")


# ============================================================================
# Request Models
# ============================================================================

class BuildRequest(BaseModel):
    """Request model for building an app preview."""
    minio_bucket: str = Field(..., description="MinIO bucket name")
    chat_id: str = Field(..., description="Chat ID")
    version: str = Field(..., description="Version or thread ID")
    ttl_hours: float = Field(1, gt=0, description="Time to live in hours")
    force_rebuild: bool = Field(
        False,
        description="Whether to force rebuild the app preview"
    )


# ============================================================================
# Build Response Models
# ============================================================================

class BuildResponseData(BaseModel):
    """Data model for build response."""
    model_config = ConfigDict(populate_by_name=True)

    build_id: str = Field(
        ...,
        alias="buildId",
        description="Unique identifier for the build"
    )
    status: BuildStatus = Field(..., description="Current status of the build")
    message: str = Field(..., description="Build message")
    # preview_url: Optional[str] = Field(None, alias="previewUrl", description="Preview URL")
    error: Optional[str] = Field(None, description="Error message")


class BuildResponse(AppPreviewResponse[BuildResponseData]):
    """Response model for build operations."""
    pass


# ============================================================================
# Logs Response Models
# ============================================================================

class LogsResponseData(BaseModel):
    """Data model for logs response."""
    model_config = ConfigDict(populate_by_name=True)

    build_id: str = Field(..., alias="buildId", description="Build ID")
    container_id: Optional[str] = Field(
        None,
        alias="containerId",
        description="Container ID"
    )
    logs: list[str] = Field(default_factory=list, description="List of log lines")
    total_lines: int = Field(0, alias="totalLines", description="Total number of log lines")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of the logs")


class LogsResponse(AppPreviewResponse[LogsResponseData]):
    """Response model for logs operations."""
    pass