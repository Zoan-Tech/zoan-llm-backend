import os, shutil
from typing import Union
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
    
    async def _get_container_file(self, container_id: str, thread_id: str, output_file: str = ".py") -> Union[Optional[str], Optional[str]]:
        """Get zip files from OpenAI container with constraint check"""
        try:
            logger.debug(f"[MinioProcessor] Games Bucket: Listing files in container {container_id}")
            response = await self.openai_client.containers.files.list(container_id=container_id, order='desc')
            
            # Count total files in OpenAI container
            # total_openai_files = len([file for file in response.data if file.path.endswith(output_file)])
            # logger.debug(f"[MinioProcessor] Games Bucket: Total OpenAI files: {total_openai_files}")
            
            # Check constraint: if thread_id provided, compare folder count with total OpenAI files
            folder_count = await self._count_folders_in_thread(thread_id)
            version = str(folder_count + 1)
            
            file_id = None
            for file in response.data:
                if file.path.endswith(output_file):
                    file_id = file.id
                    break
                
            return file_id, version
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to list container files for {container_id}: {e}")
            return None, None
    
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
            # Clean up zip file if it's a file path
            if isinstance(zip_content, str) and os.path.exists(zip_content):
                os.remove(zip_content)
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to extract and upload zip to MinIO: {e}")
            raise
        
    def _fallback_build_openai_game_file(self, file_id: str, code_interpreter_call: list, output_file=".py") -> Optional[str]:
        """Fallback method to build game file path from annotation"""
        script_globals = globals()
        script_locals = locals()
        
        data_path = f"data/{file_id}"
        if output_file == ".py":
            for code_interpreter in code_interpreter_call:
                code = code_interpreter["code"].replace("/mnt/data", data_path)
                try:
                    logger.debug(f"[MinioProcessor] Games Bucket: Executing code interpreter for file_id {file_id}")
                    exec(code, script_globals, script_locals)
                except Exception as e:
                    logger.error(f"[MinioProcessor] Games Bucket: Failed to execute code interpreter: {e}")
                    continue
            # Remove all files except build_game.py
            build_game_path = f"{data_path}/build_game.py"
            if os.path.exists(data_path):
                for filename in os.listdir(data_path):
                    file_path = os.path.join(data_path, filename)
                    if filename != "build_game.py" and os.path.isfile(file_path):
                        os.remove(file_path)
                    elif filename != "build_game.py" and os.path.isdir(file_path):
                        shutil.rmtree(file_path)

            # If build_game.py exists, use it
            if os.path.exists(build_game_path):
                return self._build_game(file_id, f"data/{file_id}/build_game.py")
        else:
            code = ""
            for game_version in code_interpreter_call["app"].keys():
                code += code_interpreter_call["app"][game_version]["code"].replace("/mnt/data", "data/{file_id}".format(file_id=file_id))
                code += "\n"
                
            logger.debug(f"[MinioProcessor] Games Bucket: Annotation: {code_interpreter_call}")
            exec(code, script_globals, script_locals)
            
            if 'zip_path' in script_locals:
                zip_file = script_locals['zip_path']
                if os.path.exists(zip_file):
                    return zip_file
            
    def _build_game(self, file_id: str, file_content: bytes | str) -> str:
        """Build game files from OpenAI container"""
        logger.debug(f"[MinioProcessor] Games Bucket: Building game files from executable Python")
        
        data_path = f"data/{file_id}"
        if type(file_content) == bytes:
        # Check if path data/minio_prefix exists
            if not os.path.exists(data_path):
                os.makedirs(data_path, exist_ok=True)
            
            # Write bytes to temporary .py file
            py_file = "build_game.py"
            py_file_path = f"{data_path}/{py_file}"
            with open(py_file_path, "wb") as f:
                f.write(file_content)
        else:
            py_file_path = file_content
        
        with open(py_file_path, "r") as f:
            file_data = f.read()
            file_data = file_data.replace("/mnt/data", data_path)
            
        with open(py_file_path, "w") as f:
            f.write(file_data)
            
        # Execute the .py file to generate game files
        import subprocess
        try:
            subprocess.run(["python", py_file_path], check=True)
            os.remove(py_file_path)  # Clean up the temporary .py file
        except subprocess.CalledProcessError as e:
            logger.error(f"[MinioProcessor] Games Bucket: Failed to execute game build script: {e}")
            raise e

        # Zip the data path
        zip_file = f"data/{file_id}.zip"
        shutil.make_archive(f"data/{file_id}", 'zip', data_path)
        # Remove the data directory 
        shutil.rmtree(data_path)
        
        return zip_file

    async def _build_openai_game_file(self, container_id: str, file_id: str, output_file: str = ".py") -> str:
        file_content = await self._download_file_from_openai(container_id, file_id)
        if output_file == ".py":
            zip_file_path = self._build_game(file_id, file_content)
        else:
            zip_file_path = file_content
            
        return zip_file_path
        
        
    async def build_openai_game_file(self, container_id: str, thread_id: str, code_interpreter_call: list, output_file: str = ".py") -> str:
        """Build game files from OpenAI container
        
        Unified flow:
        1. Get file from OpenAI container or use fallback
        2. Process based on file type:
           - .py files: Execute to generate zip file
           - .zip files: Use directly
        3. Extract and upload to MinIO
        """
        logger.debug(f"[MinioProcessor] Games Bucket: Building game files for thread {thread_id} - {container_id}")
        try:
            file_id, version = await self._get_container_file(container_id, thread_id, output_file)
            if not file_id:
                file_id = str(uuid.uuid4())
                zip_file_path = self._fallback_build_openai_game_file(file_id, code_interpreter_call, output_file)
                minio_prefix = f"{thread_id}/{version}"
            else:
                zip_file_path = await self._build_openai_game_file(container_id, file_id)
                minio_prefix = f"{thread_id}/{version}"
            
            await self._extract_and_upload_to_minio(zip_file_path, minio_prefix)
            
            return f"{self.bucket}/{minio_prefix}"
        except Exception as e:
            logger.error(f"[MinioProcessor] Games Bucket: Error building game files from container {container_id}: {e}")
            raise
        
games_processor = Processor()
