"""
connection.py — PostgreSQL Connection Pooling & Health Checks

Manages:
  • Connection pool configuration via SQLAlchemy engine
  • pgvector extension registration
  • Database connectivity ping and health checking
  • Session dependency for FastAPI routes
"""
import os
import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError

from app.config import settings

logger = logging.getLogger("db_connection")

Base = declarative_base()

_engine = None
_SessionFactory = None


def get_engine():
    """Initializes and returns the database engine with connection pooling."""
    global _engine, _SessionFactory
    if _engine is None:
        db_url = settings.DATABASE_URL
        # Ensure postgresql:// prefix (or sqlite fallback if testing locally)
        if not db_url:
            db_url = "sqlite:///./provledger.db"
            
        try:
            if db_url.startswith("sqlite"):
                _engine = create_engine(db_url, connect_args={"check_same_thread": False})
            else:
                _engine = create_engine(
                    db_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_timeout=30,
                    pool_pre_ping=True
                )
            _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
            Base.metadata.create_all(bind=_engine)
            logger.info("Database engine initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to database at {db_url}: {e}")
            _engine = create_engine("sqlite:///./fallback_provledger.db", connect_args={"check_same_thread": False})
            _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
            Base.metadata.create_all(bind=_engine)

    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        get_engine()
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions with automatic cleanup."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()


def check_db_health() -> bool:
    """Executes a simple SELECT 1 ping to verify database responsiveness."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError as e:
        logger.error(f"Database health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected database error during health check: {e}")
        return False


def init_db():
    """
    Initializes database tables and pgvector extension if PostgreSQL is active.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Try creating pgvector extension on PostgreSQL
            if engine.dialect.name == "postgresql":
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas and tables verified/created.")
    except Exception as e:
        logger.warning(f"DB initialization warning (using local fallback if needed): {e}")
