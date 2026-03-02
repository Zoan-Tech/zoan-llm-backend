"""Database models for async task tracking."""
from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SQLEnum
from datetime import datetime
import uuid
import enum

from internal.database import Base


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaDescriptionTask(Base):
    """Model for tracking media description generation tasks."""
    __tablename__ = "media_description_tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    
    # Request data
    model = Column(String(255), nullable=False)
    medias = Column(JSON, nullable=False)
    
    # Response data
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "model": self.model,
            "medias": self.medias,
            "result": self.result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
