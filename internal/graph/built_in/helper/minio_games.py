import os
from typing import Union, Literal
import mimetypes
from config.logging import get_logger
from utils.enums import *

logger = get_logger()
from services.connector.minio_service import MinioService, MinioConfig

class MinioGamesHelper(MinioService):
    def __init__(self):
        bucket = "games"
        config = MinioConfig(bucket=bucket)
        super().__init__(config)
        self.bucket = bucket
        
    def _count_folders_in_thread(self, thread_id: str) -> int:
        """Count number of folders in games/thread_id"""
        try:
            logger.debug(f"[MinioProcessor] Games Bucket: Counting folders in {thread_id}")
            prefix = f"{thread_id}/"
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=False)
            
            folder_count = 0
            for obj in objects:
                # Check if it's a folder (ends with /)
                if obj.object_name.endswith('/') and obj.object_name != prefix:
                    folder_count += 1
            
            logger.debug(f"[MinioProcessor] Games Bucket: Found {folder_count} folders in {thread_id}")
            return folder_count
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to count folders in {thread_id}: {e}")
            return 0
        
    def _download_folder(self, source_path: str, dest_path: str) -> bool:
        """Download a folder from MinIO to local path"""
        if not source_path.endswith('/'):
                source_path = source_path + '/'
            
        # Ensure dest_path is absolute or relative to current directory
        dest_path = os.path.abspath(dest_path)
        
        try:
            objects = self.client.list_objects(self.bucket, prefix=source_path, recursive=True)
            for obj in objects:
                # Get relative path after prefix
                rel_path = obj.object_name[len(source_path):]
                
                # Skip if it's just a folder placeholder or empty
                if not rel_path or rel_path.endswith('/'):
                    continue

                # Build local path safely
                local_path = os.path.join(dest_path, rel_path)
                
                # Ensure the path is still under dest_path (security check)
                local_path_abs = os.path.abspath(local_path)
                if not local_path_abs.startswith(dest_path):
                    logger.warning(f"[MinioProcessor] Games Bucket: Skipping suspicious path: {rel_path}")
                    continue

                # Ensure parent dirs exist
                parent_dir = os.path.dirname(local_path_abs)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)

                # Download file
                logger.debug(f"[MinioProcessor] Games Bucket: Downloading {obj.object_name} to {local_path_abs}")
                self.client.fget_object(self.bucket, obj.object_name, local_path_abs)
            return True
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to download {source_path}: {e}")
            return False
        
    def _download_game_version(
        self,
        source_path: str, 
        dest_path: str, 
        source_type: Union[Literal["file"], Literal["folder"]] = "file"
    ) -> bool:
        """Download the latest game version folder from games/thread_id/{version} to data_path"""
        logger.debug(f"[MinioProcessor] Games Bucket: Downloading {source_path}")
        if source_type == "folder":
            return self._download_folder(source_path, dest_path)
        else:
            try:
                filename = os.path.basename(source_path)
                local_file_path = os.path.join(dest_path, filename)
                
                # Ensure parent dirs exist
                parent_dir = os.path.dirname(local_file_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)

                logger.debug(f"[MinioProcessor] Games Bucket: Downloading file {source_path} to {local_file_path}")
                self.client.fget_object(self.bucket, source_path, local_file_path)
                return True
            except Exception as e:
                logger.error(f"[MinioProcessor] Games Bucket: Failed to download file {source_path}: {e}")
                return False
         
        
    def _upload_source_game(
        self,
        source_path: str,
        dest_path: str,
        source_type: Union[Literal["file"], Literal["folder"]] = "file"
    ) -> bool:
        """Upload source game files or folder from source_path to MinIO bucket"""
        logger.debug(f"[MinioProcessor] Games Bucket: Uploading source game {source_path} as {source_type}")
        
        if source_type == "folder":
            # Upload entire folder
            try:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        local_file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(local_file_path, source_path)
                        minio_object_path = os.path.join(dest_path, relative_path).replace("\\", "/")  # For Windows compatibility

                        # Determine content type using mimetypes module
                        content_type, _ = mimetypes.guess_type(local_file_path)
                        if content_type is None:
                            content_type = "application/octet-stream"

                        logger.debug(f"[MinioProcessor] Games Bucket: Uploading {local_file_path} to {minio_object_path}")
                        self.client.fput_object(
                            self.bucket, 
                            minio_object_path, 
                            local_file_path,
                            content_type=content_type
                        )
                return True
            except Exception as e:
                logger.error(f"[MinioProcessor] Games Bucket: Failed to upload folder {source_path}: {e}")
                return False
        else:
            # Upload single file
            try:
                # Determine content type using mimetypes module
                content_type, _ = mimetypes.guess_type(source_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                logger.debug(f"[MinioProcessor] Games Bucket: Uploading file {source_path} to {dest_path}")
                self.client.fput_object(
                    self.bucket,
                    dest_path,
                    source_path,
                    content_type=content_type
                )
                return True
            except Exception as e:
                logger.error(f"[MinioProcessor] Games Bucket: Failed to upload file {source_path}: {e}")
                return False
        
minio_games_helper = MinioGamesHelper()