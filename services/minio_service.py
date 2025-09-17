"""
MinIO Service for Game Generator

This module provides MinIO integration for uploading generated game files.
"""

import os
from config.logging import get_logger
from typing import Optional
from minio import Minio
from minio.error import S3Error
from utils.enums import *

logger = get_logger()

class MinioConfig:
    """Configuration for MinIO service"""
    def __init__(
      self,
      bucket: str,
      endpoint: Optional[str] = os.getenv(SecretEnum.MINIO_ENDPOINT.value),
      access_key: Optional[str] = os.getenv(SecretEnum.MINIO_ACCESS_KEY.value),
      secret_key: Optional[str] = os.getenv(SecretEnum.MINIO_SECRET_KEY.value),
      secure: bool = True
      ):
        self.bucket = bucket
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure

class MinioService:
    """
    MinIO service for uploading game files and folders
    """
    
    def __init__(self, config: MinioConfig):
        self.client = None
        
        if not all([config.endpoint, config.access_key, config.secret_key]):
            raise ValueError("MinIO configuration incomplete. Please provide endpoint, access_key, and secret_key.")
        
        # Initialize MinIO client
        self.client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists(config.bucket)
    
    def _ensure_bucket_exists(self, bucket: Optional[str] = None) -> None:
        """Ensure the configured bucket exists"""
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except S3Error as e:
            raise RuntimeError(f"Failed to ensure bucket exists: {e}")