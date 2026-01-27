import os
from typing import Optional
from utils.enums import SecretEnum

class Defaults:
    LOG_LEVEL = "INFO"
    
    MINIO_ENDPOINT = "localhost"
    MINIO_GAMES_BUCKET = "games"
    MINIO_LIBRARY_BUCKET = "library"
    MINIO_PORT = 9000
    MINIO_ACCESS_KEY = "minioadmin"
    MINIO_SECRET_KEY = "minioadmin"
    
    POSTGRES_CONN_STRING = "postgresql://user:password@localhost:5432/mydatabase"
    FERNET_SECRET = "your-fernet-secret"
    
    LANGFUSE_HOST = "https://api.langfuse.com"
    LANGFUSE_PROMPT_LABEL = "production"
    
    MODULE_HOST = "https://api.module.com"
    
    QDRANT_URL = "http://localhost:6333"
    QDRANT_LIBRARY_COLLECTION_NAME = "library"
    QDRANT_MESSAGES_COLLECTION_NAME = "messages"
    
    WEBHOOK_URL = "http://localhost:3000"
    
    MINIO_BROWSER_URL = f"http://{MINIO_ENDPOINT}:{MINIO_PORT}/browser"
    
    APP_PREVIEW_URL = "http://localhost:3001/api/v1"

class Config:
    # Database Configuration
    POSTGRES_CONN_STRING: str = os.environ.get(SecretEnum.POSTGRES_CONN_STRING.value, Defaults.POSTGRES_CONN_STRING)
    
    # Secret for Fernet encryption
    FERNET_SECRET: str = os.environ.get(SecretEnum.FERNET_SECRET.value, Defaults.FERNET_SECRET)

    # Langfuse Configuration
    LANGFUSE_SECRET_KEY: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value)
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value)
    LANGFUSE_HOST: str = os.environ.get(SecretEnum.LANGFUSE_HOST.value, Defaults.LANGFUSE_HOST)
    LANGFUSE_PROMPT_LABEL: str = os.environ.get(SecretEnum.LANGFUSE_PROMPT_LABEL.value, Defaults.LANGFUSE_PROMPT_LABEL)
    LANGFUSE_VERSION_ID: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_VERSION_ID.value)
    
    # Module Service
    MODULE_HOST: str = os.environ.get(SecretEnum.MODULE_HOST.value, Defaults.MODULE_HOST)
    MODULE_API_KEY: Optional[str] = os.environ.get(SecretEnum.MODULE_API_KEY.value)
    
    # MinIO Configuration
    MINIO_ACCESS_KEY: str = os.environ.get(SecretEnum.MINIO_ACCESS_KEY.value, Defaults.MINIO_ACCESS_KEY)
    MINIO_SECRET_KEY: str = os.environ.get(SecretEnum.MINIO_SECRET_KEY.value, Defaults.MINIO_SECRET_KEY)
    MINIO_ENDPOINT: str = os.environ.get(SecretEnum.MINIO_ENDPOINT.value)
    MINIO_PORT: int = int(os.environ.get(SecretEnum.MINIO_PORT.value, Defaults.MINIO_PORT))
    MINIO_GAMES_BUCKET: str = os.environ.get(SecretEnum.MINIO_GAMES_BUCKET.value, Defaults.MINIO_GAMES_BUCKET)
    MINIO_LIBRARY_BUCKET: str = os.environ.get(SecretEnum.MINIO_LIBRARY_BUCKET.value, Defaults.MINIO_LIBRARY_BUCKET)
    MINIO_BROWSER_URL: str = os.environ.get(SecretEnum.MINIO_BROWSER_URL.value, Defaults.MINIO_BROWSER_URL)
    
    # Model API Keys
    OPENAI_API_KEY: Optional[str] = os.environ.get(SecretEnum.OPENAI_API_KEY.value)
    ANTHROPIC_API_KEY: Optional[str] = os.environ.get(SecretEnum.ANTHROPIC_API_KEY.value)
    
    # Qdrant Configuration
    QDRANT_URL: str = os.environ.get(SecretEnum.QDRANT_URL.value, Defaults.QDRANT_URL)
    QDRANT_API_KEY: Optional[str] = os.environ.get(SecretEnum.QDRANT_API_KEY.value)
    QDRANT_LIBRARY_COLLECTION_NAME: str = os.environ.get(SecretEnum.QDRANT_LIBRARY_COLLECTION_NAME.value, Defaults.QDRANT_LIBRARY_COLLECTION_NAME)
    QDRANT_MESSAGES_COLLECTION_NAME: str = os.environ.get(SecretEnum.QDRANT_MESSAGES_COLLECTION_NAME.value, Defaults.QDRANT_MESSAGES_COLLECTION_NAME)
    
    # FE Settings
    WEBHOOK_URL: str = os.environ.get(SecretEnum.WEBHOOK_URL.value, Defaults.WEBHOOK_URL)
    
    # Preview API URL
    APP_PREVIEW_URL: str = os.environ.get(SecretEnum.APP_PREVIEW_URL.value, Defaults.APP_PREVIEW_URL)
    
    # Kafka Configuration
    KAFKA_BROKERS: str = os.environ.get(SecretEnum.KAFKA_BROKERS.value)
    KAFKA_GROUP_ID: str = os.environ.get(SecretEnum.KAFKA_GROUP_ID.value)
    KAFKA_AGENT_MENTION_TOPIC: str = os.environ.get(SecretEnum.KAFKA_AGENT_MENTION_TOPIC.value)
    KAFKA_AGENT_REPLY_TOPIC: str = os.environ.get(SecretEnum.KAFKA_AGENT_REPLY_TOPIC.value)
    
    # Extra Settings
    MAX_WORKERS: int = int(os.environ.get(SecretEnum.MAX_WORKERS.value, 10))
    GRPC_PORT: int = int(os.environ.get(SecretEnum.GRPC_PORT.value, 50051))    
    LOG_LEVEL: str = os.environ.get(SecretEnum.LOG_LEVEL.value, Defaults.LOG_LEVEL)