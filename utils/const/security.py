"""Security constants for request handling and validation."""
from typing import Set

# HTTP Request Configuration
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
MAX_FILE_SIZE_MB = 50  # Maximum file size to download
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# URL Validation
ALLOWED_URL_SCHEMES: Set[str] = {"http", "https"}
BLOCKED_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS metadata service
    "metadata.google.internal",  # GCP metadata service
    "169.254.169.250",  # Azure metadata service
}
