"""Pydantic schemas for API request / response serialization."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Run schemas
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32, examples=["NVDA"])
    trade_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-01-15"])
    llm_provider: str = Field(default="openai")
    deep_think_llm: str = Field(default="gpt-5.4")
    quick_think_llm: str = Field(default="gpt-5.4-mini")
    selected_analysts: List[str] = Field(default=["market", "social", "news", "fundamentals"])
    max_debate_rounds: int = Field(default=1, ge=1, le=5)
    max_risk_discuss_rounds: int = Field(default=1, ge=1, le=5)
    output_language: str = Field(default="English")


class RunEventResponse(BaseModel):
    id: int
    agent_name: Optional[str] = None
    event_type: str
    payload: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    id: str
    ticker: str
    trade_date: str
    status: str
    config_snapshot: Optional[Any] = None
    final_decision: Optional[str] = None
    result_json: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    events: List[RunEventResponse] = []

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    id: str
    ticker: str
    trade_date: str
    status: str
    final_decision: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Config schemas
# ---------------------------------------------------------------------------

class ConfigResponse(BaseModel):
    config: dict


class ConfigUpdate(BaseModel):
    config: dict


class SavedConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    config_json: dict


class SavedConfigResponse(BaseModel):
    id: int
    name: str
    config_json: dict
    is_default: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Provider schemas
# ---------------------------------------------------------------------------

class ModelOption(BaseModel):
    label: str
    value: str


class ProviderModels(BaseModel):
    provider: str
    quick: List[ModelOption]
    deep: List[ModelOption]


class ProviderListItem(BaseModel):
    name: str
    display_name: str
    requires_key: bool
    env_var: Optional[str] = None
