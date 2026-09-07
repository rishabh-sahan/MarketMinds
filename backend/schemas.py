"""Pydantic schemas for API request / response serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional, Any, Dict, List

from pydantic import BaseModel, Field, PlainSerializer


def _as_utc_iso(value: Optional[datetime]) -> Optional[str]:
    """Serialize a timestamp as ISO-8601 that states its timezone.

    Every timestamp is written with ``datetime.now(timezone.utc)``, but the
    columns are ``DateTime`` without ``timezone=True``, so both SQLite and
    Postgres hand them back naive. Pydantic then rendered them as
    ``2026-09-07T18:21:57`` — a UTC instant with nothing saying so.

    JavaScript reads a bare ISO string as *local* time, so the browser placed
    every timestamp UTC-offset hours away from where it belonged. In IST that
    made a run that had just started report an elapsed time of 5h30m, exactly
    the offset. Stamping the offset here fixes it for every consumer at once,
    rather than each caller remembering to append a "Z".
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


# Use for any timestamp crossing the API boundary.
UTCDateTime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=Optional[str])]


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

    # Caller-supplied provider credential. Used for this run only: it is
    # deliberately absent from RunResponse, never written to config_snapshot,
    # and never logged, so a deployed instance can run entirely on keys its
    # visitors bring without ever becoming custodian of them.
    api_key: Optional[str] = Field(default=None, exclude=True, repr=False)

    # -- Advanced ----------------------------------------------------------
    # Custom endpoint, for self-hosted or proxied OpenAI-compatible
    # gateways. None leaves each provider client on its own default.
    backend_url: Optional[str] = Field(default=None)
    # Mapped onto the provider's own thinking knob (openai_reasoning_effort,
    # google_thinking_level, or anthropic_effort) at config-build time.
    reasoning_effort: Optional[str] = Field(default=None, examples=["medium"])
    checkpoint_enabled: bool = Field(default=False)
    data_vendors: Optional[Dict[str, str]] = Field(default=None)
    news_article_limit: Optional[int] = Field(default=None, ge=1, le=100)
    global_news_article_limit: Optional[int] = Field(default=None, ge=1, le=100)
    global_news_lookback_days: Optional[int] = Field(default=None, ge=1, le=90)


class RunEventResponse(BaseModel):
    id: int
    agent_name: Optional[str] = None
    event_type: str
    payload: Optional[Any] = None
    timestamp: UTCDateTime

    class Config:
        from_attributes = True


class RunUsage(BaseModel):
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


class RunResponse(BaseModel):
    id: str
    ticker: str
    trade_date: str
    status: str
    config_snapshot: Optional[Any] = None
    final_decision: Optional[str] = None
    result_json: Optional[Any] = None
    error_message: Optional[str] = None
    agent_status: Optional[Dict[str, str]] = None
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: UTCDateTime
    started_at: Optional[UTCDateTime] = None
    completed_at: Optional[UTCDateTime] = None
    events: List[RunEventResponse] = []

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    id: str
    ticker: str
    trade_date: str
    status: str
    final_decision: Optional[str] = None
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: UTCDateTime
    completed_at: Optional[UTCDateTime] = None

    class Config:
        from_attributes = True


class RunStatsResponse(BaseModel):
    """Aggregate counters across every stored run, for the dashboard."""

    total: int = 0
    completed: int = 0
    running: int = 0
    failed: int = 0
    cancelled: int = 0
    pending: int = 0
    # Rating label -> count, over completed runs.
    rating_counts: Dict[str, int] = Field(default_factory=dict)
    # Ticker -> run count, most analysed first.
    top_tickers: List[Dict[str, Any]] = Field(default_factory=list)
    # ISO date -> run count, for the activity sparkline.
    runs_per_day: List[Dict[str, Any]] = Field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    avg_duration_seconds: Optional[float] = None


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
    created_at: UTCDateTime

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
    # Whether the key is actually present in the environment, so the UI can
    # warn before launching a run that would fail on its first API call.
    has_key: bool = False


# ---------------------------------------------------------------------------
# Memory / reflection schemas
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    """One decision from the trading memory log, with its resolved outcome."""

    ticker: str
    date: str
    rating: Optional[str] = None
    decision: Optional[str] = None
    status: str = "pending"          # pending | resolved
    raw_return: Optional[float] = None
    alpha_return: Optional[float] = None
    holding_days: Optional[int] = None
    benchmark: Optional[str] = None
    reflection: Optional[str] = None


class MemoryResponse(BaseModel):
    # Where the log lives — a file path for a local checkout, or a description
    # of the table for a deployed instance. Shown so it is never a mystery
    # which store the page is reading.
    path: str
    exists: bool
    entries: List[MemoryEntry] = Field(default_factory=list)
    total: int = 0
    resolved: int = 0
    pending: int = 0
    # Entries across every user. Reads are shared — a run learns from the whole
    # pool — while `total` above counts only the caller's own. Surfaced so the
    # page can say so rather than looking as though entries went missing.
    pool_total: int = 0
    # Mean realised alpha across resolved entries, and the hit rate of
    # directional calls that moved the right way.
    avg_alpha: Optional[float] = None
    avg_raw_return: Optional[float] = None
