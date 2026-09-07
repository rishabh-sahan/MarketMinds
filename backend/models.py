"""SQLAlchemy ORM models for runs, events, and saved configs."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, ForeignKey, JSON,
)
from sqlalchemy.dialects.postgresql import JSONB

# Reports, config snapshots and event payloads are all JSON documents. On
# PostgreSQL they are stored as JSONB — binary, indexable, and queryable —
# while SQLite keeps the portable JSON type. `with_variant` picks per dialect,
# so the models stay single-sourced.
JSONDoc = JSON().with_variant(JSONB(), "postgresql")
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_id():
    return uuid.uuid4().hex


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(32), primary_key=True, default=_new_id)

    # Supabase auth user id (the JWT's `sub`). Null means the run predates
    # authentication, or was created by a deployment that has none — those
    # stay visible to nobody but remain in the table rather than being
    # rewritten to a guessed owner.
    user_id = Column(String(64), nullable=True, index=True)

    # Featured on the signed-out dashboard as a read-only demo. Off by
    # default: a run is private to its creator unless deliberately published.
    is_public = Column(Integer, nullable=False, default=0, server_default="0")

    ticker = Column(String(32), nullable=False, index=True)
    trade_date = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    config_snapshot = Column(JSONDoc, nullable=True)
    final_decision = Column(Text, nullable=True)
    result_json = Column(JSONDoc, nullable=True)
    error_message = Column(Text, nullable=True)

    # Live pipeline snapshot: {agent_name: pending|running|completed}. Persisted
    # so reopening a run mid-flight restores the pipeline view instead of
    # showing every agent as pending until the next event arrives.
    agent_status = Column(JSONDoc, nullable=True)

    # Usage counters accumulated by the LangChain stats callback.
    llm_calls = Column(Integer, nullable=False, default=0, server_default="0")
    tool_calls = Column(Integer, nullable=False, default=0, server_default="0")
    tokens_in = Column(Integer, nullable=False, default=0, server_default="0")
    tokens_out = Column(Integer, nullable=False, default=0, server_default="0")

    created_at = Column(DateTime, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.timestamp")


class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(32), ForeignKey("runs.id"), nullable=False, index=True)
    agent_name = Column(String(64), nullable=True)
    event_type = Column(String(32), nullable=False)  # agent_start, agent_complete, tool_call, report_update, error, info
    payload = Column(JSONDoc, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)

    run = relationship("Run", back_populates="events")


class MemoryLogEntry(Base):
    """One decision in the trading decision log.

    This is the markdown decision log turned into rows. The file version is
    still used by the CLI; a deployed instance keeps it here instead, because
    the log is the one piece of state whose loss makes later analyses worse
    and a container's disk does not survive a restart.

    Reads are shared and writes are private: every run's Portfolio Manager
    learns from the whole table, while the Memory page shows a user only the
    entries they created. So the pool keeps improving for everyone without
    one user's history showing up in another's UI.

    An entry is written pending — the decision is known, the outcome is not.
    A later run for the same ticker fetches the realised return, fills the
    outcome columns and writes the reflection. ``resolved_at`` is the single
    marker of which state an entry is in.
    """

    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=True, index=True)

    ticker = Column(String(32), nullable=False, index=True)
    trade_date = Column(String(10), nullable=False, index=True)
    rating = Column(String(16), nullable=True)
    decision = Column(Text, nullable=False)

    # Outcome — all null until a later run resolves the entry. Stored as
    # numbers rather than the file log's "+3.2%" strings, because in a real
    # database a return is a number and the UI would only parse them back.
    raw_return = Column(Float, nullable=True)
    alpha_return = Column(Float, nullable=True)
    holding_days = Column(Integer, nullable=True)
    reflection = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)


class SavedConfig(Base):
    __tablename__ = "saved_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    config_json = Column(JSONDoc, nullable=False)
    is_default = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
