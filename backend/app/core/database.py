"""
app/core/database.py
────────────────────
SQLAlchemy engine + session factory.
Uses synchronous psycopg2 driver (compatible with Celery workers).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # detect stale connections gracefully
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and ensures cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
