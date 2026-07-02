"""Database connection and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL statements if debug=True
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max overflow connections
    pool_pre_ping=True,  # Check connections before using
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Get database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database (create tables)."""
    from app.models import Base

    Base.metadata.create_all(bind=engine)
