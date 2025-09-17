import os
import zipfile
from config.logging import get_logger
from io import BytesIO
from typing import Optional
from services.minio_service import MinioService, MinioConfig
from openai import AsyncOpenAI
import uuid
from utils.enums import *

logger = get_logger()

DEFAULT_GAME_BUCKET = "games"
class Processor(MinioService):
    openai_client = AsyncOpenAI()
    
    def __init__(self, minio_config: Optional[MinioConfig] = None):
        if minio_config is None:
            minio_config = MinioConfig(bucket=DEFAULT_GAME_BUCKET)
        super().__init__(minio_config)
        self.bucket = minio_config.bucket
    
    async def _get_container_zip_file(self, container_id: str) -> Optional[str]:
        """Get zip files from OpenAI container"""
        try:
            logger.debug(f"[MinioProcessor] Games Bucket: Listing files in container {container_id}")
            response = await self.openai_client.containers.files.list(container_id=container_id, order='desc')
            zip_file_id = None
            for file in response.data:
                if file.path.endswith('.zip'):
                    zip_file_id = file.id
                    break
                
            return zip_file_id
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to list container files for {container_id}: {e}")
            raise
    
    async def _download_file_from_openai(self, container_id: str, file_id: str) -> bytes:
        """Download file content from OpenAI Files API"""
        logger.debug(f"[MinioProcessor] Games Bucket: Downloading file {file_id} from container {container_id}")
        try:
            response = await self.openai_client.containers.files.content.retrieve(container_id=container_id, file_id=file_id)
            return response.read()
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to download file {file_id}: {e}")
            raise
    
    def _unzip_to_directory(self, zip_content: bytes, extract_path: str) -> None:
        """Unzip content to directory"""
        logger.debug(f"[MinioProcessor] Games Bucket: Unzipping content to {extract_path}")
        os.makedirs(extract_path, exist_ok=True)
        
        with zipfile.ZipFile(BytesIO(zip_content), 'r') as zip_ref:
            zip_ref.extractall(extract_path)
    
    async def _extract_and_upload_to_minio(self, zip_content: bytes, prefix: str) -> None:
        """Extract zip content and upload individual files directly to MinIO"""
        logger.debug(f"[MinioProcessor] Games Bucket: Extracting and uploading zip contents to MinIO")
        try:
            import mimetypes
            
            with zipfile.ZipFile(BytesIO(zip_content), 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if not file_info.is_dir():
                        # Read file content from zip
                        file_content = zip_ref.read(file_info.filename)
                        
                        # Create object name with prefix
                        object_name = f"{prefix}/{file_info.filename}".replace("\\", "/")
                        
                        # Determine MIME type
                        content_type, _ = mimetypes.guess_type(file_info.filename)
                        if content_type is None:
                            content_type = "application/octet-stream"
                        
                        # Upload file content directly to MinIO
                        file_stream = BytesIO(file_content)
                        self.client.put_object(
                            self.bucket,
                            object_name,
                            file_stream,
                            length=len(file_content),
                            content_type=content_type,
                            metadata={
                                "Content-Disposition": 'inline'
                            }
                        )
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to extract and upload zip to MinIO: {e}")
            raise
    
    async def build_openai_game_file(self, container_id: str, thread_id: str) -> str:
        """Build game files from OpenAI container"""
        logger.debug(f"[MinioProcessor] Games Bucket: Building game files for thread {thread_id} - {container_id}")
        try:
            zip_file_id = await self._get_container_zip_file(container_id)
            if not zip_file_id:
                raise Exception(f"No zip files found in container {container_id}")

            zip_content = await self._download_file_from_openai(container_id, zip_file_id)
            game_version = uuid.uuid4()
            minio_prefix = f"{thread_id}/{game_version}"
            await self._extract_and_upload_to_minio(zip_content, minio_prefix)
            
            return minio_prefix
                        
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Error building game files from container {container_id}: {e}")
            raise
        
DEFAULT_GAMES_PROCESSOR = Processor()