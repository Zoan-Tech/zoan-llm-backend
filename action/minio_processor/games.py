import os
import zipfile
from config.logging import get_logger
from io import BytesIO
from typing import Optional
from services.connector.minio_service import MinioService, MinioConfig
from openai import AsyncOpenAI
import uuid
from utils.enums import *
from config import Config

logger = get_logger()

class Processor(MinioService):
    openai_client = AsyncOpenAI(
        api_key=Config.OPENAI_API_KEY,
    )
    
    def __init__(self, minio_config: Optional[MinioConfig] = None):
        if minio_config is None:
            bucket = Config.MINIO_GAMES_BUCKET
            minio_config = MinioConfig(bucket=bucket)
            
        super().__init__(minio_config)
        self.bucket = minio_config.bucket
        self.openai_client = AsyncOpenAI()
    
    async def _count_folders_in_thread(self, thread_id: str) -> int:
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
    
    async def _get_container_zip_file(self, container_id: str, thread_id: str) -> Optional[str]:
        """Get zip files from OpenAI container with constraint check"""
        try:
            logger.debug(f"[MinioProcessor] Games Bucket: Listing files in container {container_id}")
            response = await self.openai_client.containers.files.list(container_id=container_id, order='desc')
            
            # Count total files in OpenAI container
            total_openai_files = len([file for file in response.data if file.path.endswith('.zip')])
            logger.debug(f"[MinioProcessor] Games Bucket: Total OpenAI files: {total_openai_files}")
            
            # Check constraint: if thread_id provided, compare folder count with total OpenAI files
            folder_count = await self._count_folders_in_thread(thread_id)
            if folder_count >= total_openai_files:
                logger.info(f"[MinioProcessor] No new game version to upload.")
                return None
            
            zip_file_id = None
            for file in response.data:
                if file.path.endswith('.zip'):
                    zip_file_id = file.id
                    break
                
            return zip_file_id
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to list container files for {container_id}: {e}")
            return None
    
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
    
    async def _extract_and_upload_to_minio(self, zip_content: bytes | str, prefix: str) -> None:
        """Extract zip content and upload individual files directly to MinIO"""
        logger.debug(f"[MinioProcessor] Games Bucket: Extracting and uploading zip contents to MinIO")
        try:
            import mimetypes
            
            zip_ref = zipfile.ZipFile(BytesIO(zip_content)) if isinstance(zip_content, bytes) else zipfile.ZipFile(zip_content)
            file_names = [n.replace("\\", "/") for n in zip_ref.namelist() if not n.endswith("/")]
            roots = {n.split("/", 1)[0] for n in file_names if "/" in n}
            has_single_root = len(roots) == 1 and all("/" in n for n in file_names)
            for file_info in zip_ref.infolist():
                if not file_info.is_dir():
                    # Read file content from zip
                    file_content = zip_ref.read(file_info.filename)
                    
                    # Create object name with prefix
                    object_name = f"{prefix}/{file_info.filename}".replace("\\", "/") if not has_single_root else f"{prefix}/{'/'.join(file_info.filename.split('/')[1:])}"
                    
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
            zip_ref.close()
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to extract and upload zip to MinIO: {e}")
            raise
        
    def _fallback_build_openai_game_file(self, thread_id: str, annotation: dict) -> Optional[str]:
        """Fallback method to build game file path from annotation"""
        script_globals = globals()
        script_locals = locals()

        code = ""
        for game_version in annotation["app"].keys():
            code += annotation["app"][game_version]["code"].replace("/mnt/data", "data/{thread_id}".format(thread_id=thread_id))
            code += "\n"
            
        logger.debug(f"[MinioProcessor] Games Bucket: Annotation: {annotation}")
        exec(code, script_globals, script_locals)
        
        if 'zip_path' in script_locals:
            zip_file = script_locals['zip_path']
            if os.path.exists(zip_file):
                return zip_file
        
    async def build_openai_game_file(self, container_id: str, thread_id: str, annotation: dict) -> str:
        """Build game files from OpenAI container"""
        logger.debug(f"[MinioProcessor] Games Bucket: Building game files for thread {thread_id} - {container_id}")
        try:
            zip_file_id = await self._get_container_zip_file(container_id, thread_id)
            if not zip_file_id:
                zip_content = self._fallback_build_openai_game_file(thread_id, annotation)
                if not zip_content:
                    raise Exception("No container ID provided for building game files.")
                minio_prefix = f"{thread_id}/{uuid.uuid4()}"
            else:
                zip_content = await self._download_file_from_openai(container_id, zip_file_id)
                minio_prefix = f"{thread_id}/{zip_file_id}"
                
            await self._extract_and_upload_to_minio(zip_content, minio_prefix)
            
            if type(zip_content) is str:
                import shutil
                folder_path = os.path.dirname(zip_content)
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
            
            return "{bucket}/{prefix}".format(bucket=self.bucket, prefix=minio_prefix)
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Error building game files from container {container_id}: {e}")
            raise
        
games_processor = Processor()
