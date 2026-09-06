"""SQLAlchemy engine and session factory for SQLite."""

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

logger = logging.getLogger(__name__)


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
    a new column to a table an older build already created. Rather than pull
    in a migration framework for a single-file dev database, new columns are
    reconciled here with additive ``ALTER TABLE`` statements, which SQLite
    supports cheaply and which are safe to re-run.
    """
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
