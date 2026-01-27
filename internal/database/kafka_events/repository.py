"""Repository for Kafka events database operations."""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from internal.database.kafka_events.models import KafkaEvent, EventStatus


class KafkaEventRepository:
    """Repository for Kafka event operations."""
    
    @staticmethod
    def create_event(
        db: Session,
        topic: str,
        message_key: Optional[str],
        message_value: str,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        headers: Optional[dict] = None,
        consumer_name: Optional[str] = None,
        max_retries: int = 3,
    ) -> KafkaEvent:
        """
        Create a new Kafka event.
        
        Args:
            db: Database session
            topic: Kafka topic name
            message_key: Message key
            message_value: Message value (JSON string)
            partition: Kafka partition
            offset: Kafka offset
            headers: Message headers
            consumer_name: Name of the consumer
            max_retries: Maximum number of retry attempts
        
        Returns:
            Created KafkaEvent
        """
        event = KafkaEvent(
            topic=topic,
            partition=partition,
            offset=offset,
            message_key=message_key,
            message_value=message_value,
            headers=headers,
            status=EventStatus.PENDING,
            retry_count=0,
            max_retries=max_retries,
            consumer_name=consumer_name,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def get_event(db: Session, event_id: UUID) -> Optional[KafkaEvent]:
        """Get event by ID."""
        return db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
    
    @staticmethod
    def get_pending_events(
        db: Session,
        limit: int = 10,
        topic: Optional[str] = None,
    ) -> List[KafkaEvent]:
        """
        Get pending events for processing.
        
        Args:
            db: Database session
            limit: Maximum number of events to return
            topic: Filter by specific topic (optional)
        
        Returns:
            List of pending KafkaEvents
        """
        query = db.query(KafkaEvent).filter(
            KafkaEvent.status == EventStatus.PENDING
        )
        
        if topic:
            query = query.filter(KafkaEvent.topic == topic)
        
        return (
            query
            .order_by(KafkaEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .all()
        )
    
    @staticmethod
    def update_event_status(
        db: Session,
        event_id: UUID,
        status: EventStatus,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
    ) -> Optional[KafkaEvent]:
        """
        Update event status.
        
        Args:
            db: Database session
            event_id: Event ID
            status: New status
            error_message: Error message (if failed)
            error_traceback: Error traceback (if failed)
        
        Returns:
            Updated KafkaEvent or None if not found
        """
        event = db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
        if not event:
            return None
        
        event.status = status
        event.updated_at = datetime.utcnow()
        
        if status == EventStatus.PROCESSING and not event.processing_started_at:
            event.processing_started_at = datetime.utcnow()
        
        if status in (EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.DEAD_LETTER):
            event.completed_at = datetime.utcnow()
        
        if error_message is not None:
            event.last_error = error_message
        
        if error_traceback is not None:
            event.error_traceback = error_traceback
        
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def mark_processing(db: Session, event_id: UUID) -> Optional[KafkaEvent]:
        """
        Mark event as processing.
        
        Args:
            db: Database session
            event_id: Event ID
        
        Returns:
            Updated KafkaEvent or None if not found
        """
        event = db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
        if not event:
            return None
        
        event.status = EventStatus.PROCESSING
        event.processing_started_at = datetime.utcnow()
        event.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def mark_completed(db: Session, event_id: UUID) -> Optional[KafkaEvent]:
        """
        Mark event as completed.
        
        Args:
            db: Database session
            event_id: Event ID
        
        Returns:
            Updated KafkaEvent or None if not found
        """
        event = db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
        if not event:
            return None
        
        event.status = EventStatus.COMPLETED
        event.completed_at = datetime.utcnow()
        event.updated_at = datetime.utcnow()
        event.last_error = None
        event.error_traceback = None
        
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def mark_failed(
        db: Session,
        event_id: UUID,
        error_message: str,
        error_traceback: Optional[str] = None,
        increment_retry: bool = True,
    ) -> Optional[KafkaEvent]:
        """
        Mark event as failed and handle retry logic.
        
        Args:
            db: Database session
            event_id: Event ID
            error_message: Error message
            error_traceback: Error traceback
            increment_retry: Whether to increment retry count
        
        Returns:
            Updated KafkaEvent or None if not found
        """
        event = db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
        if not event:
            return None
        
        if increment_retry:
            event.retry_count += 1
        
        event.last_error = error_message
        event.error_traceback = error_traceback
        event.updated_at = datetime.utcnow()
        
        # Check if max retries exceeded
        if event.retry_count >= event.max_retries:
            event.status = EventStatus.DEAD_LETTER
            event.completed_at = datetime.utcnow()
        else:
            # Reset to pending for retry
            event.status = EventStatus.PENDING
            event.processing_started_at = None
        
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def get_stuck_events(
        db: Session,
        timeout_seconds: int = 300,
        limit: int = 100,
    ) -> List[KafkaEvent]:
        """
        Get events stuck in PROCESSING state.
        
        Args:
            db: Database session
            timeout_seconds: Timeout threshold in seconds
            limit: Maximum number of events to return
        
        Returns:
            List of stuck KafkaEvents
        """
        timeout_threshold = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        
        return (
            db.query(KafkaEvent)
            .filter(
                and_(
                    KafkaEvent.status == EventStatus.PROCESSING,
                    KafkaEvent.processing_started_at < timeout_threshold
                )
            )
            .limit(limit)
            .all()
        )
    
    @staticmethod
    def reset_stuck_event(db: Session, event_id: UUID) -> Optional[KafkaEvent]:
        """
        Reset a stuck event to pending status.
        
        Args:
            db: Database session
            event_id: Event ID
        
        Returns:
            Updated KafkaEvent or None if not found
        """
        event = db.query(KafkaEvent).filter(KafkaEvent.id == event_id).first()
        if not event:
            return None
        
        event.retry_count += 1
        event.last_error = f"Processing timeout - reset from stuck state"
        event.updated_at = datetime.utcnow()
        
        # Check if max retries exceeded
        if event.retry_count >= event.max_retries:
            event.status = EventStatus.DEAD_LETTER
            event.completed_at = datetime.utcnow()
        else:
            event.status = EventStatus.PENDING
            event.processing_started_at = None
        
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def get_events_by_status(
        db: Session,
        status: EventStatus,
        limit: int = 100,
        topic: Optional[str] = None,
    ) -> List[KafkaEvent]:
        """
        Get events by status.
        
        Args:
            db: Database session
            status: Event status to filter by
            limit: Maximum number of events to return
            topic: Filter by specific topic (optional)
        
        Returns:
            List of KafkaEvents
        """
        query = db.query(KafkaEvent).filter(KafkaEvent.status == status)
        
        if topic:
            query = query.filter(KafkaEvent.topic == topic)
        
        return query.order_by(KafkaEvent.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def delete_old_events(
        db: Session,
        days_old: int = 30,
        status: Optional[EventStatus] = EventStatus.COMPLETED,
    ) -> int:
        """
        Delete old events (for cleanup).
        
        Args:
            db: Database session
            days_old: Delete events older than this many days
            status: Filter by status (default: COMPLETED)
        
        Returns:
            Number of deleted events
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        query = db.query(KafkaEvent).filter(KafkaEvent.created_at < cutoff_date)
        
        if status:
            query = query.filter(KafkaEvent.status == status)
        
        count = query.count()
        query.delete(synchronize_session=False)
        db.commit()
        
        return count
