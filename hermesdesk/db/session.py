"""Short-lived SQLAlchemy sessions."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from hermesdesk.config import DATABASE_URL

connect_args = {}
engine_kwargs = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args

engine = create_engine(DATABASE_URL, **engine_kwargs)

if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    from hermesdesk.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "user" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("user")}
    statements = []
    if "is_banned" not in columns:
        statements.append("ALTER TABLE user ADD COLUMN is_banned BOOLEAN DEFAULT 0")
    if "created_at" not in columns:
        statements.append("ALTER TABLE user ADD COLUMN created_at DATETIME")
    if "last_seen_at" not in columns:
        statements.append("ALTER TABLE user ADD COLUMN last_seen_at DATETIME")
    if not statements:
        return
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


@contextmanager
def get_session() -> Iterator[Session]:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
