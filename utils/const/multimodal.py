from typing import List

IMAGE_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp"]
PDF_MIME_TYPES: List[str] = ["application/pdf"]
AUDIO_MIME_TYPES: List[str] = ["audio/mpeg", "audio/wav", "audio/ogg"]
VIDEO_MIME_TYPES: List[str] = ["video/mp4", "video/webm", "video/ogg"]
DOCS_MIME_TYPES: List[str] = [
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
]

# Multimodal Processing
VECTOR_DIMENSION = 1536
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_SCORE_THRESHOLD = 0.7
PAGINATION_OFFSET_MULTIPLIER = 10

# Document Processing
MAX_DOCUMENT_SIZE_MB = 50
DOCUMENT_PROCESSING_TIMEOUT = 300  # seconds
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"