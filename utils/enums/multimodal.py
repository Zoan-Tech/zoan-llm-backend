"""Enum definitions for multimodal processing."""
from enum import Enum


class MultimodalType(str, Enum):
    """Types of multimodal content supported by the completion system."""
    IMAGE = "image"
    PDF = "file"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class ChunkProcessingStatus(str, Enum):
    """Status of chunk processing."""
    STORED = "stored"
    FAILED = "failed"
    PENDING = "pending"
