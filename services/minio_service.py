"""
MinIO Service for Game Generator

This module provides MinIO integration for uploading generated game files.
"""

import os
from config.logging import get_logger
from typing import Optional
from pathlib import Path
from minio import Minio
from minio.error import S3Error
import mimetypes

logger = get_logger()

class MinioConfig:
    """Configuration for MinIO service"""
    def __init__(
      self,
      bucket: str,
      endpoint: Optional[str] = os.getenv("MINIO_ENDPOINT"),
      access_key: Optional[str] = os.getenv("MINIO_ACCESS_KEY") ,
      secret_key: Optional[str] = os.getenv("MINIO_SECRET_KEY"),
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
        self.config = config
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
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the configured bucket exists"""
        try:
            if not self.client.bucket_exists(self.config.bucket):
                self.client.make_bucket(self.config.bucket)
        except S3Error as e:
            raise RuntimeError(f"Failed to ensure bucket exists: {e}")
    
    async def upload_folder_with_prefix(self, folder_path: str, prefix: str) -> str:
        """
        Upload a folder to MinIO with a given prefix
        
        Args:
            folder_path: Local path to the folder to upload
            prefix: Prefix to use in MinIO (e.g., thread_id)
            
        Returns:
            Base path for the uploaded content
        """
        logger.info(f"[MinioService] Starting folder upload: {folder_path} with prefix: {prefix}")
        try:
            folder_path = Path(folder_path)
            if not folder_path.exists():
                raise FileNotFoundError(f"Folder not found: {folder_path}")
            
            uploaded_files = []
            
            # Walk through all files in the folder
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path from the base folder
                    relative_path = file_path.relative_to(folder_path)
                    
                    # Create object name with prefix
                    object_name = f"{prefix}/{relative_path}".replace("\\", "/")
                    
                    # Upload the file
                    # Determine MIME type based on file extension
                    content_type, _ = mimetypes.guess_type(str(file_path))
                    if content_type is None:
                      content_type = "application/octet-stream"
                    
                    self.client.fput_object(
                      self.config.bucket,
                      object_name,
                      str(file_path),
                      content_type=content_type,
                      metadata={
                        "Content-Disposition": 'inline'
                      }
                    )
                    
                    uploaded_files.append(object_name)
            
            # Return the base path for the uploaded content
            return f"{self.config.bucket}/{prefix}"
            
        except Exception as e:
            logger.error(f"[MinioService] Error uploading folder to MinIO: {e}")
            raise
    
    def upload_file(self, local_file_path: str, object_name: str) -> str:
        """
        Upload a single file to MinIO
        
        Args:
            local_file_path: Path to the local file
            object_name: Name for the object in MinIO
            
        Returns:
            Object name in MinIO
        """
        logger.info(f"[MinioService] Starting file upload: {local_file_path} as {object_name}")
        try:
            self.client.fput_object(
                self.config.bucket,
                object_name,
                local_file_path
            )
            return f"{self.config.bucket}/{object_name}"
        except Exception as e:
            logger.error(f"[MinioService] Error uploading file to MinIO: {e}")
            raise
    
    def get_file_url(self, object_name: str, expires_in_days: int = 7) -> str:
        """
        Get a presigned URL for a file in MinIO
        
        Args:
            object_name: Name of the object in MinIO
            expires_in_days: Number of days the URL should be valid
            
        Returns:
            Presigned URL for the file
        """
        logger.info(f"[MinioService] Generating presigned URL for: {object_name}")
        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                self.config.bucket,
                object_name,
                expires=timedelta(days=expires_in_days)
            )
            return url
        except Exception as e:
            logger.error(f"[MinioService] Error generating presigned URL: {e}")
            raise
    
    def list_objects(self, prefix: str = None) -> list:
        """
        List objects in the bucket with optional prefix
        
        Args:
            prefix: Optional prefix to filter objects
            
        Returns:
            List of object names
        """
        logger.info(f"[MinioService] Listing objects with prefix: {prefix}")
        try:
            objects = self.client.list_objects(
                self.config.bucket,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"[MinioService] Error listing objects: {e}")
            raise