"""Utility functions for secure HTTP requests and URL validation."""
from urllib.parse import urlparse
import httpx
from typing import Optional
from config.logging import get_logger
from utils.const.security import (
    DEFAULT_REQUEST_TIMEOUT,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_URL_SCHEMES,
    BLOCKED_HOSTS,
)

logger = get_logger()


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL for security concerns.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            return False, f"Invalid URL scheme: {parsed.scheme}. Only {ALLOWED_URL_SCHEMES} allowed."
        
        # Check hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "URL must have a valid hostname"
        
        # Check against blocked hosts
        if hostname.lower() in BLOCKED_HOSTS or hostname.startswith("169.254."):
            return False, f"URL hostname is blocked for security reasons: {hostname}"
        
        # Check for private IP ranges (basic check)
        if hostname.startswith(("10.", "172.", "192.168.")):
            return False, f"Private IP addresses are not allowed: {hostname}"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"


def safe_http_get(
    url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    max_size: int = MAX_FILE_SIZE_BYTES,
) -> Optional[bytes]:
    """
    Safely download content from a URL with security checks.
    
    Args:
        url: URL to download from
        timeout: Request timeout in seconds
        max_size: Maximum allowed content size in bytes
        
    Returns:
        Content bytes if successful, None if failed
    """
    # Validate URL
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        logger.error(f"URL validation failed: {error_msg}")
        return None
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, follow_redirects=True)
            
            # Check status
            if response.status_code != 200:
                logger.error(f"Failed to download from {url}: status {response.status_code}")
                return None
            
            # Check content length header before downloading
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > max_size:
                        logger.error(
                            f"File too large: {content_length} bytes (max: {max_size})"
                        )
                        return None
                except ValueError:
                    logger.warning(f"Invalid content-length header: {content_length}")
            
            # Download with size limit
            content = b""
            for chunk in response.iter_bytes(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    logger.error(
                        f"Downloaded content exceeded max size: {len(content)} bytes (max: {max_size})"
                    )
                    return None
            
            return content
            
    except httpx.TimeoutException:
        logger.error(f"Request timeout while downloading from {url}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error downloading from {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error downloading from {url}: {str(e)}")
        return None
