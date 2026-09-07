"""SQLAlchemy engine and session factory.

Runs on SQLite by default — a single file needs no server and is the right
choice for local and single-user use. Set ``DATABASE_URL`` to a PostgreSQL DSN
to switch, which is what a deployed instance should do: a container's local
disk is usually ephemeral, and SQLite takes a write lock on the whole file, so
it does not survive more than one process.

Everything above this layer is plain ORM, so the switch is a URL and the
engine options assembled below.
"""

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

IS_SQLITE = DATABASE_URL.startswith("sqlite")


def _engine_options() -> dict:
    """Engine arguments appropriate to the backing database."""
    if IS_SQLITE:
        return {
            # Runs execute on a background thread, which is a different thread
            # from the one that opened the connection.
            "connect_args": {"check_same_thread": False},
        }

    # Managed Postgres tiers drop idle connections; pre-ping replaces a dead
    # one transparently instead of surfacing it as a failed request, and
    # recycling keeps connections well under the usual idle timeout.
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
    }


engine = create_engine(DATABASE_URL, echo=False, **_engine_options())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables and add any columns missing from an existing DB.

    ``create_all`` only creates tables that do not exist yet — it will not add
    a new column to a table an older build already created. Rather than pull a
    migration framework into a project whose schema changes rarely, new columns
    are reconciled here with additive ``ALTER TABLE`` statements: supported by
    both SQLite and PostgreSQL, and safe to re-run.

    This handles additions only. A rename, a type change or a drop needs a real
    migration tool (Alembic) — this deliberately does not attempt them, because
    guessing at destructive DDL is worse than failing loudly.
    """
    # Importing the models is what registers them on Base.metadata. Without
    # this, `create_all` finds an empty metadata and creates nothing at all —
    # succeeding silently, which is the worst way to fail. The app happens to
    # import models earlier via its routers; a script or a test calling this
    # directly does not.
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Add columns declared on the models but absent from the live schema."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"{column.name} {column.type.compile(engine.dialect)}"
                # Existing rows need a value, so only defaulted columns can be
                # added NOT NULL; everything else is added nullable.
                if column.server_default is not None:
                    ddl += f" NOT NULL DEFAULT {column.server_default.arg}"
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))
                logger.info("Added column %s.%s", table.name, column.name)
