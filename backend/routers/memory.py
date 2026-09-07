"""Memory router — exposes the trading decision log and its reflections.

Every completed run appends its decision to the log. On a later run for the
same ticker the realised return is fetched (raw, plus alpha against the Indian
benchmark), a reflection is generated, and that history is injected into the
Portfolio Manager's prompt. This router surfaces the log read-only so the web
app can show what the system has learned.

Two stores exist. A deployed instance keeps entries as rows, which is what
survives a container restart; a local checkout with no database rows falls
back to reading the markdown file, so a developer's existing log still shows
up. The file path is reported either way so it is never unclear which is
being read.

**Reads are shared, display is private.** Every run learns from every entry,
but this endpoint returns only the caller's own — with ``pool_total`` saying
how large the shared pool is, so a user with two entries can see that the
system is drawing on more than that rather than concluding entries were lost.
"""

from __future__ import annotations

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.auth import AuthUser, auth_enabled, optional_user
from backend.database import get_db
from backend.models import MemoryLogEntry
from backend.schemas import MemoryEntry, MemoryResponse

router = APIRouter(prefix="/api/memory", tags=["memory"])

# The file log stores percentages as "+3.2%" and holding periods as "5d".
_PCT_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*%$")
_DAYS_RE = re.compile(r"^(\d+)\s*d$")


def _parse_pct(value: Optional[str]) -> Optional[float]:
    """Turn a '+3.2%' tag field into a fraction (0.032)."""
    if not value:
        return None
    match = _PCT_RE.match(str(value).strip())
    return float(match.group(1)) / 100.0 if match else None


def _parse_days(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = _DAYS_RE.match(str(value).strip())
    return int(match.group(1)) if match else None


def _from_row(row: MemoryLogEntry, benchmark: Optional[str]) -> MemoryEntry:
    return MemoryEntry(
        ticker=row.ticker,
        date=row.trade_date,
        rating=row.rating,
        decision=row.decision or None,
        status="pending" if row.resolved_at is None else "resolved",
        raw_return=row.raw_return,
        alpha_return=row.alpha_return,
        holding_days=row.holding_days,
        benchmark=benchmark,
        reflection=row.reflection or None,
    )


def _from_file_entry(raw: dict, benchmark: Optional[str]) -> MemoryEntry:
    return MemoryEntry(
        ticker=raw.get("ticker", ""),
        date=raw.get("date", ""),
        rating=raw.get("rating"),
        decision=raw.get("decision") or None,
        status="pending" if raw.get("pending") else "resolved",
        raw_return=_parse_pct(raw.get("raw")),
        alpha_return=_parse_pct(raw.get("alpha")),
        holding_days=_parse_days(raw.get("holding")),
        benchmark=benchmark,
        reflection=raw.get("reflection") or None,
    )


@router.get("", response_model=MemoryResponse)
def get_memory(
    ticker: Optional[str] = Query(None, description="Filter to one ticker"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(optional_user),
):
    """Return decision-log entries the caller owns, most recent first."""
    from marketminds.default_config import DEFAULT_CONFIG

    benchmark = DEFAULT_CONFIG.get("benchmark_ticker")
    pool_total = db.query(MemoryLogEntry).count()

    if pool_total:
        query = db.query(MemoryLogEntry)
        # On an authenticated instance a user sees only their own entries.
        # With no auth configured there is one operator, so scoping would only
        # hide their own history from them.
        if auth_enabled():
            query = query.filter(
                MemoryLogEntry.user_id == (user.id if user else None)
            )
        if ticker:
            query = query.filter(MemoryLogEntry.ticker == ticker.upper())

        rows = query.order_by(MemoryLogEntry.id.desc()).all()
        entries: List[MemoryEntry] = [_from_row(r, benchmark) for r in rows]
        path = "Database — memory_entries table"
        exists = True
    else:
        # No rows yet: fall back to the markdown log so a local checkout with
        # existing history is not shown an empty page.
        from marketminds.agents.utils.memory import TradingMemoryLog

        log = TradingMemoryLog(DEFAULT_CONFIG)
        path = str(DEFAULT_CONFIG.get("memory_log_path", ""))
        raw_entries = log.load_entries()
        if ticker:
            wanted = ticker.upper()
            raw_entries = [
                e for e in raw_entries
                if (e.get("ticker") or "").upper() == wanted
            ]
        # The file log is append-only and therefore chronological; newest
        # first reads better in the UI.
        entries = [_from_file_entry(e, benchmark) for e in reversed(raw_entries)]
        exists = bool(raw_entries)
        pool_total = len(entries)

    resolved = [e for e in entries if e.status == "resolved"]
    alphas = [e.alpha_return for e in resolved if e.alpha_return is not None]
    raws = [e.raw_return for e in resolved if e.raw_return is not None]

    return MemoryResponse(
        path=path,
        exists=exists,
        entries=entries[:limit],
        total=len(entries),
        resolved=len(resolved),
        pending=len(entries) - len(resolved),
        pool_total=pool_total,
        avg_alpha=(sum(alphas) / len(alphas)) if alphas else None,
        avg_raw_return=(sum(raws) / len(raws)) if raws else None,
    )
