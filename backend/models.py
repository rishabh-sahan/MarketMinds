"""SQLAlchemy ORM models for runs, events, and saved configs."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_id():
    return uuid.uuid4().hex


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(32), primary_key=True, default=_new_id)
    ticker = Column(String(32), nullable=False, index=True)
    trade_date = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    config_snapshot = Column(JSON, nullable=True)
    final_decision = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
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
    payload = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)

    run = relationship("Run", back_populates="events")


class SavedConfig(Base):
    __tablename__ = "saved_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    config_json = Column(JSON, nullable=False)
    is_default = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
