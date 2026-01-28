"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config

# Create SQLAlchemy engine
engine = create_engine(
    Config.POSTGRES_CONN_STRING,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from internal.database.media_description.models import MediaDescriptionTask
    from internal.database.kafka_events.models import KafkaEvent
    
    Base.metadata.create_all(bind=engine)
