from services.connector.minio_service import MinioService, MinioConfig

class MinioLibraryClient:
    """Minio client for library bucket"""
    def __init__(self):
        config = MinioConfig(bucket="library")
        self.client = MinioService(config).client

minio_library_client = MinioLibraryClient()