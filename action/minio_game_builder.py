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
    
    async def build_openai_game_file(self, container_id: str, extract_path: str, thread_id: str) -> None:
        """Build game files from OpenAI container"""
        logger.info(f"{logger_prefix} Building game files for thread {thread_id}")
        try:
            zip_file_ids = await self._get_container_zip_files(container_id)
            if not zip_file_ids:
                return

            for file_id in zip_file_ids:
                zip_content = await self._download_file_from_openai(container_id, file_id)
                self._unzip_to_directory(zip_content, extract_path)
            
            # Upload unzipped files to MinIO if available
            if self.minio_available and self.minio_service:
                upload_result = await self.minio_service.upload_folder_with_prefix(extract_path, prefix=thread_id)
                # Remove local folder after successful upload
                try:
                    shutil.rmtree(extract_path)
                except Exception as cleanup_error:
                    logger.error(f"{logger_prefix} Failed to remove local folder {extract_path}: {cleanup_error}")
            else:
                logger.info(f"{logger_prefix} MinIO service not available, files saved locally only")
                        
        except Exception as e:
            logger.error(f"{logger_prefix} Error building game files from container {container_id}: {e}")
            raise