"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # Verify connection is alive before using
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    from database.models import Base
    Base.metadata.create_all(bind=engine)
