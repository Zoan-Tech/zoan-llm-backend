import os
import httpx
import zipfile
import shutil
import logging
from io import BytesIO
from typing import List
from services.minio_service import MinioService, MinioConfig

logger = logging.getLogger(__name__)
logger_prefix = "[minio_game_builder]"

class MinioGameBuilder:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    def __init__(self):
        try:
            minio_config = MinioConfig(
                bucket=os.getenv("MINIO_GAMES_BUCKET", "builds")
            )
            self.minio_service = MinioService(config=minio_config)
            self.minio_available = True
            logger.info(f"{logger_prefix} MinIO service initialized successfully")
        except Exception as e:
            logger.error(f"{logger_prefix} Failed to initialize MinIO service: {e}")
            self.minio_service = None
            self.minio_available = False
    
    async def _get_container_zip_files(self, container_id: str) -> List[str]:
        """Get zip files from OpenAI container"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.openai.com/v1/containers/{container_id}/files",
                    headers={"Authorization": f"Bearer {self.OPENAI_API_KEY}"}
                )
                
                result = response.json()
                zip_file_ids = []
                
                if result.get('data') and isinstance(result['data'], list):
                    for file in result['data']:
                        if file.get('path', '').endswith('.zip'):
                            zip_file_ids.append(file['id'])
                
                return zip_file_ids
        except Exception as e:
            logger.error(f"{logger_prefix} Failed to list container files for {container_id}: {e}")
            raise
    
    async def _download_file_from_openai(self, container_id: str, file_id: str) -> bytes:
        """Download file content from OpenAI Files API"""
        logger.info(f"{logger_prefix} Downloading file {file_id} from container {container_id}")
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.openai.com/v1/containers/{container_id}/files/{file_id}/content"
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.OPENAI_API_KEY}"}
                )
                
                if response.status_code != 200:
                    raise Exception(f"HTTP error! status: {response.status_code}")
                
                return response.content
        except Exception as e:
            logger.error(f"{logger_prefix} Failed to download file {file_id}: {e}")
            raise
    
    def _unzip_to_directory(self, zip_content: bytes, extract_path: str) -> None:
        """Unzip content to directory"""
        logger.info(f"{logger_prefix} Unzipping content to {extract_path}")
        os.makedirs(extract_path, exist_ok=True)
        
        with zipfile.ZipFile(BytesIO(zip_content), 'r') as zip_ref:
            zip_ref.extractall(extract_path)
    
    async def _extract_and_upload_to_minio(self, zip_content: bytes, prefix: str) -> None:
        """Extract zip content and upload individual files directly to MinIO"""
        logger.info(f"{logger_prefix} Extracting and uploading zip contents to MinIO")
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
                        self.minio_service.client.put_object(
                            self.minio_service.config.bucket,
                            object_name,
                            file_stream,
                            length=len(file_content),
                            content_type=content_type,
                            metadata={
                                "Content-Disposition": 'inline'
                            }
                        )
        except Exception as e:
            logger.error(f"{logger_prefix} Failed to extract and upload zip to MinIO: {e}")
            raise
    
    async def build_openai_game_file(self, container_id: str, thread_id: str) -> None:
        """Build game files from OpenAI container"""
        logger.info(f"{logger_prefix} Building game files for thread {thread_id}")
        try:
            zip_file_ids = await self._get_container_zip_files(container_id)
            if not zip_file_ids:
                raise Exception(f"No zip files found in container {container_id}")

            for file_id in zip_file_ids:
                zip_content = await self._download_file_from_openai(container_id, file_id)
                await self._extract_and_upload_to_minio(zip_content, thread_id)
                        
        except Exception as e:
            logger.error(f"{logger_prefix} Error building game files from container {container_id}: {e}")
            raise