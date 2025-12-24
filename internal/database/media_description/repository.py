"""Repository for database operations."""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from internal.database.media_description.models import MediaDescriptionTask, TaskStatus


class MediaDescriptionTaskRepository:
    """Repository for media description task operations."""
    
    @staticmethod
    def create_task(db: Session, model: str, medias: list[str]) -> MediaDescriptionTask:
        """Create a new task."""
        task = MediaDescriptionTask(
            model=model,
            medias=medias,
            status=TaskStatus.PENDING,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    
    @staticmethod
    def get_task(db: Session, task_id: str) -> Optional[MediaDescriptionTask]:
        """Get task by ID."""
        return db.query(MediaDescriptionTask).filter(MediaDescriptionTask.task_id == task_id).first()
    
    @staticmethod
    def update_task_status(
        db: Session,
        task_id: str,
        status: TaskStatus,
        result: Optional[list] = None,
        error_message: Optional[str] = None,
    ) -> Optional[MediaDescriptionTask]:
        """Update task status and result."""
        task = db.query(MediaDescriptionTask).filter(MediaDescriptionTask.task_id == task_id).first()
        if not task:
            return None
        
        task.status = status
        
        if status == TaskStatus.PROCESSING and not task.started_at:
            task.started_at = datetime.utcnow()
        
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.utcnow()
        
        if result is not None:
            task.result = result
        
        if error_message is not None:
            task.error_message = error_message
        
        db.commit()
        db.refresh(task)
        return task
    
    @staticmethod
    def get_pending_tasks(db: Session, limit: int = 10) -> list[MediaDescriptionTask]:
        """Get pending tasks for processing."""
        return (
            db.query(MediaDescriptionTask)
            .filter(MediaDescriptionTask.status == TaskStatus.PENDING)
            .order_by(MediaDescriptionTask.created_at)
            .limit(limit)
            .all()
        )
