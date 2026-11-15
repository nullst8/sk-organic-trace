import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "provenance.db"
# Default to local SQLite; override with DATABASE_URL (e.g. a Postgres connection
# string) when deployed. The schema is plain SQLAlchemy and is Postgres-ready.
def _normalise_url(url: str) -> str:
    """Point bare postgres URLs (Neon, Render, Heroku style) at the psycopg driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalise_url(os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_kwargs: dict = {}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Re-validate pooled connections, which can go stale when a serverless
    # Postgres (e.g. Neon) scales to zero between requests.
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_on_connect(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_extras() -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_events_seq ON events (seq)")
        )
