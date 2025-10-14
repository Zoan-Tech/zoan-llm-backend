import os
from typing import Optional
from utils.enums import SecretEnum

class Defaults:
    LOG_LEVEL = "INFO"
    MINIO_GAMES_BUCKET = "games"
    MINIO_LIBRARY_BUCKET = "library"
    MINIO_PORT = 9000
    MINIO_ACCESS_KEY = "minioadmin"
    MINIO_SECRET_KEY = "minioadmin"
    
    KAFKA_TOPIC_REQUEST = "llm.channel.completion"
    KAFKA_TOPIC_RESPONSE = "llm.channel.response"
    KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
    KAFKA_GROUP_ID = "llm_channel_group"
    KAFKA_TOPIC_MINIO_NOTIFY = "minio.notifications"
    
    POSTGRES_CONN_STRING = "postgresql://user:password@localhost:5432/mydatabase"
    FERNET_SECRET = "your-fernet-secret"
    
    LANGFUSE_HOST = "https://api.langfuse.com"
    LANGFUSE_PROMPT_LABEL = "production"
    
    MODULE_HOST = "https://api.module.com"
    
    QDRANT_URL = "http://localhost:6333"
    QDRANT_LIBRARY_COLLECTION_NAME = "library"
    
    WEBHOOK_URL = "http://localhost:3000"

class Config:
    POSTGRES_CONN_STRING: str = os.environ.get(SecretEnum.POSTGRES_CONN_STRING.value, Defaults.POSTGRES_CONN_STRING)
    FERNET_SECRET: str = os.environ.get(SecretEnum.FERNET_SECRET.value, Defaults.FERNET_SECRET)

    LANGFUSE_SECRET_KEY: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_SECRET_KEY.value)
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_PUBLIC_KEY.value)
    LANGFUSE_HOST: str = os.environ.get(SecretEnum.LANGFUSE_HOST.value, Defaults.LANGFUSE_HOST)
    LANGFUSE_PROMPT_LABEL: str = os.environ.get(SecretEnum.LANGFUSE_PROMPT_LABEL.value, Defaults.LANGFUSE_PROMPT_LABEL)
    LANGFUSE_VERSION_ID: Optional[str] = os.environ.get(SecretEnum.LANGFUSE_VERSION_ID.value)
    

    MODULE_HOST: str = os.environ.get(SecretEnum.MODULE_HOST.value, Defaults.MODULE_HOST)
    MODULE_API_KEY: Optional[str] = os.environ.get(SecretEnum.MODULE_API_KEY.value)

    OPENAI_API_KEY: Optional[str] = os.environ.get(SecretEnum.OPENAI_API_KEY.value)
    ANTHROPIC_API_KEY: Optional[str] = os.environ.get(SecretEnum.ANTHROPIC_API_KEY.value)
    
    LOG_LEVEL: str = os.environ.get(SecretEnum.LOG_LEVEL.value, Defaults.LOG_LEVEL)

    MINIO_ACCESS_KEY: str = os.environ.get(SecretEnum.MINIO_ACCESS_KEY.value, Defaults.MINIO_ACCESS_KEY)
    MINIO_SECRET_KEY: str = os.environ.get(SecretEnum.MINIO_SECRET_KEY.value, Defaults.MINIO_SECRET_KEY)
    MINIO_ENDPOINT: str = os.environ.get(SecretEnum.MINIO_ENDPOINT.value)
    MINIO_PORT: int = int(os.environ.get(SecretEnum.MINIO_PORT.value, Defaults.MINIO_PORT))
    MINIO_GAMES_BUCKET: str = os.environ.get(SecretEnum.MINIO_GAMES_BUCKET.value, Defaults.MINIO_GAMES_BUCKET)
    MINIO_LIBRARY_BUCKET: str = os.environ.get(SecretEnum.MINIO_LIBRARY_BUCKET.value, Defaults.MINIO_LIBRARY_BUCKET)
    MINIO_BROWSER_URL: str = os.environ.get(SecretEnum.MINIO_BROWSER_URL.value, f"http://{MINIO_ENDPOINT}:{MINIO_PORT}/browser")

    KAFKA_BOOTSTRAP_SERVERS: str = os.environ.get(SecretEnum.KAFKA_BOOTSTRAP_SERVERS.value, Defaults.KAFKA_BOOTSTRAP_SERVERS)
    KAFKA_TOPIC_REQUEST: str = os.environ.get(SecretEnum.KAFKA_TOPIC_REQUEST.value, Defaults.KAFKA_TOPIC_REQUEST)
    KAFKA_TOPIC_RESPONSE: str = os.environ.get(SecretEnum.KAFKA_TOPIC_RESPONSE.value, Defaults.KAFKA_TOPIC_RESPONSE)
    KAFKA_GROUP_ID: str = os.environ.get(SecretEnum.KAFKA_GROUP_ID.value, Defaults.KAFKA_GROUP_ID)
    KAFKA_TOPIC_MINIO_NOTIFY: str = os.environ.get(SecretEnum.KAFKA_TOPIC_MINIO_NOTIFY.value, Defaults.KAFKA_TOPIC_MINIO_NOTIFY)
    
    QDRANT_URL: str = os.environ.get(SecretEnum.QDRANT_URL.value, Defaults.QDRANT_URL)
    QDRANT_API_KEY: Optional[str] = os.environ.get(SecretEnum.QDRANT_API_KEY.value)
    QDRANT_LIBRARY_COLLECTION_NAME: str = os.environ.get(SecretEnum.QDRANT_LIBRARY_COLLECTION_NAME.value, Defaults.QDRANT_LIBRARY_COLLECTION_NAME)
    
    WEBHOOK_URL: str = os.environ.get(SecretEnum.WEBHOOK_URL.value, Defaults.WEBHOOK_URL)