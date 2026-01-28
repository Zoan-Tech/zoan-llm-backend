"""Database models for Kafka events."""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, DateTime, Enum, Integer, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from internal.database import Base


class EventStatus(str, PyEnum):
    """Status of a Kafka event."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class KafkaEvent(Base):
    """
    Model for storing Kafka events to be processed asynchronously.
    
    This table acts as a persistent queue where:
    1. Consumers save incoming messages immediately
    2. Worker polls for pending events and processes them
    3. Events track processing status and retry attempts
    """
    __tablename__ = "kafka_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Event identification
    topic = Column(String(255), nullable=False, index=True)
    partition = Column(Integer, nullable=True)
    offset = Column(Integer, nullable=True)
    message_key = Column(String(255), nullable=True, index=True)
    
    # Message content
    message_value = Column(Text, nullable=False)  # JSON string
    headers = Column(JSON, nullable=True)
    
    # Processing metadata
    status = Column(
        Enum(EventStatus, native_enum=False),
        nullable=False,
        default=EventStatus.PENDING,
        index=True,
    )
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Consumer identification
    consumer_name = Column(String(255), nullable=True)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_kafka_events_status_created', 'status', 'created_at'),
        Index('idx_kafka_events_topic_status', 'topic', 'status'),
        Index('idx_kafka_events_processing', 'status', 'processing_started_at'),
    )
    
    def __repr__(self):
        return (
            f"<KafkaEvent(id={self.id}, topic={self.topic}, "
            f"status={self.status}, retry={self.retry_count})>"
        )
