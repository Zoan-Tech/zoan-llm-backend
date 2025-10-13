from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class UserIdentity(BaseModel):
    """User identity information for S3 requests."""
    principal_id: str = Field(..., alias="principalId")
    
    class Config:
        validate_by_name = True


class RequestParameters(BaseModel):
    """Parameters of the S3 request."""
    principal_id: str = Field(..., alias="principalId")
    region: str
    source_ip_address: str = Field(..., alias="sourceIPAddress")
    
    class Config:
        validate_by_name = True


class ResponseElements(BaseModel):
    """Elements from the S3 response."""
    x_amz_request_id: Optional[str] = Field(None, alias="x-amz-request-id")
    x_minio_origin_endpoint: Optional[str] = Field(None, alias="x-minio-origin-endpoint")
    
    class Config:
        validate_by_name = True

class BucketInfo(BaseModel):
    """Information about the S3 bucket."""
    name: str
    owner_identity: UserIdentity = Field(..., alias="ownerIdentity")
    arn: str
    
    class Config:
        validate_by_name = True


class ObjectInfo(BaseModel):
    """Information about the S3 object."""
    key: str
    size: Optional[int] = None
    e_tag: Optional[str] = Field(None, alias="eTag")
    content_type: Optional[str] = Field(None, alias="contentType")
    user_metadata: Dict[str, Any] = Field(default_factory=dict, alias="userMetadata")
    sequencer: str
    
    class Config:
        validate_by_name = True


class S3Info(BaseModel):
    """S3-specific information for the notification."""
    s3_schema_version: str = Field(..., alias="s3SchemaVersion")
    configuration_id: str = Field(..., alias="configurationId")
    bucket: BucketInfo
    object: ObjectInfo
    
    class Config:
        validate_by_name = True


class Source(BaseModel):
    """Source information for the notification."""
    host: str
    port: str = ""
    user_agent: str = Field(default="", alias="userAgent")
    
    class Config:
        validate_by_name = True


class NotificationRecord(BaseModel):
    """A single notification record from S3/MinIO."""
    event_version: str = Field(..., alias="eventVersion")
    event_source: str = Field(..., alias="eventSource")
    aws_region: str = Field(..., alias="awsRegion")
    event_time: str = Field(..., alias="eventTime")
    event_name: str = Field(..., alias="eventName")
    user_identity: UserIdentity = Field(..., alias="userIdentity")
    request_parameters: RequestParameters = Field(..., alias="requestParameters")
    response_elements: ResponseElements = Field(..., alias="responseElements")
    s3: S3Info
    source: Source
    
    class Config:
        validate_by_name = True


class BucketNotification(BaseModel):
    """S3/MinIO bucket notification containing one or more records."""
    event_name: str = Field(..., alias="EventName")
    key: str = Field(..., alias="Key")
    records: List[NotificationRecord] = Field(..., alias="Records")
    
    class Config:
        validate_by_name = True
    
    def get_bucket_name(self) -> str:
        """Get the bucket name from the first record."""
        return self.key.split('/')[0]
    
    def get_owner(self) -> str:
        """Get the owner from the first record."""
        owner = self.key.split('/')[1]
        return owner if owner != "assets" else "public"
    
    def get_object_key(self) -> str:
        """Get the object key from the first record."""
        return '/'.join(self.key.split('/')[1:])  
    
    def get_mimetype(self) -> str:
        """Get the mimetype from the first record."""
        if self.records:
            return self.records[0].s3.object.content_type
        return "application/octet-stream"
    
    def is_created_event(self) -> bool:
        """Check if this is a creation event."""
        return self.event_name.startswith("s3:ObjectCreated")
    
    def is_removed_event(self) -> bool:
        """Check if this is a removal event."""
        return self.event_name.startswith("s3:ObjectRemoved")


class QdrantPayload(BaseModel):
    """Payload structure for Qdrant vector database."""
    bucket: str
    object_key: str
    owner: str
    mimetype: str