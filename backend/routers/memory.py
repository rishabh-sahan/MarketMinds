"""Memory router — exposes the trading decision log and its reflections.

Every completed run appends its decision to an append-only markdown log. On a
later run for the same ticker the realised return is fetched (raw, plus alpha
against a regional benchmark), a reflection is generated, and that history is
injected into the Portfolio Manager's prompt. This router surfaces that log
read-only so the web app can show what the system has learned.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Query

from backend.schemas import MemoryEntry, MemoryResponse

router = APIRouter(prefix="/api/memory", tags=["memory"])

# Tag fields store percentages as "+3.2%" and holding periods as "5d".
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


@router.get("", response_model=MemoryResponse)
def get_memory(
    ticker: Optional[str] = Query(None, description="Filter to one ticker"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Return decision-log entries, most recent first."""
    from marketminds.agents.utils.memory import TradingMemoryLog
    from marketminds.default_config import DEFAULT_CONFIG

    log = TradingMemoryLog(DEFAULT_CONFIG)
    path = str(DEFAULT_CONFIG.get("memory_log_path", ""))
    raw_entries = log.load_entries()

    if ticker:
        wanted = ticker.upper()
        raw_entries = [e for e in raw_entries if (e.get("ticker") or "").upper() == wanted]

    entries = []
    for raw in raw_entries:
        entries.append(
            MemoryEntry(
                ticker=raw.get("ticker", ""),
                date=raw.get("date", ""),
                rating=raw.get("rating"),
                decision=raw.get("decision") or None,
                status="pending" if raw.get("pending") else "resolved",
                raw_return=_parse_pct(raw.get("raw")),
                alpha_return=_parse_pct(raw.get("alpha")),
                holding_days=_parse_days(raw.get("holding")),
                benchmark=DEFAULT_CONFIG.get("benchmark_ticker"),
                reflection=raw.get("reflection") or None,
            )
        )

    # The log is append-only and therefore chronological; newest first reads
    # better in the UI.
    entries.reverse()

    resolved = [e for e in entries if e.status == "resolved"]
    alphas = [e.alpha_return for e in resolved if e.alpha_return is not None]
    raws = [e.raw_return for e in resolved if e.raw_return is not None]

    return MemoryResponse(
        path=path,
        exists=bool(raw_entries),
        entries=entries[:limit],
        total=len(entries),
        resolved=len(resolved),
        pending=len(entries) - len(resolved),
        avg_alpha=(sum(alphas) / len(alphas)) if alphas else None,
        avg_raw_return=(sum(raws) / len(raws)) if raws else None,
    )
