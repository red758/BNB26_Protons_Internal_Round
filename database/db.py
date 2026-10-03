"""Database engine and session handling (SQLAlchemy 2.x). SQLite by default, Postgres via DATABASE_URL."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def init_db(app) -> None:
    global _engine, _Session

    url = app.config["DATABASE_URL"]
    if url.startswith("postgres://"):  # some hosts still hand out the old scheme
        url = url.replace("postgres://", "postgresql://", 1)

    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_engine(url, **kwargs)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)

    from database import models  # noqa: F401  (registers tables on Base)

    Base.metadata.create_all(_engine)


@contextmanager
def session_scope():
    """Commit on success, roll back on error, always close."""
    if _Session is None:
        raise RuntimeError("Database not initialised. Call init_db(app) first.")
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()