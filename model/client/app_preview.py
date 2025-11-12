from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, Optional, TypeVar
from typing import Literal

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

class BuildStatus(StrEnum):
    STARTING = "starting"
    BUILDING = "building"
    RUNNING  = "running"
    FAILED   = "failed"
    STOPPED  = "stopped"
    DELETED  = "deleted"


class BuildRequest(BaseModel):
    minio_bucket: str = Field(..., description="MinIO bucket name")
    chat_id: str = Field(..., description="Chat ID")
    version: str = Field(..., description="Version or thread ID")
    ttl_hours: float = Field(1, gt=0, description="Time to live in hours")
    force_rebuild: bool = Field(False, description="Whether to force rebuild the app preview")


class BuildResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    build_id: str = Field(..., alias="buildId", description="Unique identifier for the build")
    status: BuildStatus = Field(..., description="Current status of the build")
    message: str = Field(..., description="Build message")
    # preview_url: Optional[str] = Field(None, alias="previewUrl", description="Preview URL")
    error: Optional[str] = Field(None, description="Error message")


class AppPreviewResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["OK", "NOT_FOUND", "ERROR", "INVALID"] = Field(..., description="Overall result")
    data: T | list[T] | None = Field(
        None, description="Payload for the response; may be a single item, a list, or null"
    )
    message: str = Field(..., description="More details about the request outcome")
    error: dict[str, Any] | None = Field(None, description="Error details if any")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")


class BuildResponse(AppPreviewResponse[BuildResponseData]):
    pass


class LogsResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    build_id: str = Field(..., alias="buildId", description="Build ID")
    container_id: Optional[str] = Field(None, alias="containerId", description="Container ID")
    logs: list[str] = Field(default_factory=list, description="List of log lines")
    total_lines: int = Field(0, alias="totalLines", description="Total number of log lines")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of the logs")


class LogsResponse(AppPreviewResponse[LogsResponseData]):
    pass