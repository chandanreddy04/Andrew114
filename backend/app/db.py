"""The PostgreSQL connection. Each API request gets its own session."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        # Tests only: one shared in-memory database across threads.
        from sqlalchemy import event
        from sqlalchemy.pool import StaticPool

        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        # SQLite only honours "on delete cascade" with this switched on.
        event.listen(engine, "connect", lambda conn, _: conn.execute("pragma foreign_keys=on"))
        return engine
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
