"""Live Indian market context — indices, sectors, currency and commodities.

A single stock is only readable against the tape it trades on. This module
assembles that backdrop: where the broad indices closed, how the sector
indices moved, what volatility is doing, and the global inputs Indian
equities are most sensitive to — the rupee, crude, gold, US yields and the
dollar index.

All figures come from Yahoo Finance, the same source as the price history,
so the numbers an analyst sees here reconcile with its own candles. Every
lookup degrades to a "not available" row instead of raising, so one dead
symbol never costs the whole snapshot.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from .india import (
    BROAD_INDICES,
    MACRO_INSTRUMENTS,
    SECTOR_INDICES,
    VOLATILITY_INDEX,
)

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """A close plus its trailing moves, or a reason it is missing."""

    label: str
    symbol: str
    last: Optional[float] = None
    change_1d: Optional[float] = None
    change_5d: Optional[float] = None
    change_1m: Optional[float] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.last is not None


def _pct(series, periods: int) -> Optional[float]:
    """Percent change over ``periods`` sessions, or None if too short."""
    if len(series) <= periods:
        return None
    prior = series.iloc[-(periods + 1)]
    if not prior:
        return None
    return float((series.iloc[-1] / prior - 1) * 100)


def _quote(label: str, symbol: str, as_of: Optional[str] = None) -> Quote:
    """Fetch one instrument's recent history and derive its moves."""
    try:
        import yfinance as yf

        # ~130 calendar days is comfortably more than the 21 sessions the
        # 1-month change needs, even across a run of exchange holidays;
        # anchored to `as_of` so a backdated run is not shown today's tape.
        if as_of:
            end = datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)
            start = end - timedelta(days=130)
            hist = yf.Ticker(symbol).history(
                start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d")
            )
        else:
            hist = yf.Ticker(symbol).history(period="3mo")

        if hist is None or hist.empty:
            return Quote(label, symbol, error="no data")

        close = hist["Close"].dropna()
        if close.empty:
            return Quote(label, symbol, error="no closes")

        return Quote(
            label=label,
            symbol=symbol,
            last=float(close.iloc[-1]),
            change_1d=_pct(close, 1),
            change_5d=_pct(close, 5),
            change_1m=_pct(close, 21),
        )
    except Exception as exc:
        logger.info("Quote failed for %s (%s): %s", label, symbol, exc)
        return Quote(label, symbol, error=type(exc).__name__)


def _quote_group(group: Dict[str, str], as_of: Optional[str]) -> List[Quote]:
    """Fetch a labelled group of symbols concurrently."""
    items = list(group.items())
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
        return list(pool.map(lambda kv: _quote(kv[0], kv[1], as_of), items))


def _table(title: str, quotes: Sequence[Quote], unit: str = "") -> str:
    """Render quotes as a markdown table, noting any that failed."""
    rows = [q for q in quotes if q.ok]
    missing = [q for q in quotes if not q.ok]

    if not rows:
        return f"### {title}\n\nNot available.\n"

    def fmt(v):
        return "—" if v is None else f"{v:+.2f}%"

    lines = [
        f"### {title}",
        "",
        "| Instrument | Last | 1D | 1W | 1M |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for q in rows:
        lines.append(
            f"| {q.label} | {q.last:,.2f}{unit} | {fmt(q.change_1d)} | "
            f"{fmt(q.change_5d)} | {fmt(q.change_1m)} |"
        )
    if missing:
        lines.append("")
        lines.append(f"*Unavailable: {', '.join(q.label for q in missing)}*")
    lines.append("")
    return "\n".join(lines)


def get_market_context(as_of: Optional[str] = None, include_sectors: bool = True) -> str:
    """Assemble the full Indian market backdrop as a markdown block.

    ``as_of`` anchors every series to the analysis date so a backdated run
    reads the tape as it stood then, not as it stands now.
    """
    broad = _quote_group(BROAD_INDICES, as_of)
    vix = _quote_group(VOLATILITY_INDEX, as_of)
    macro = _quote_group(MACRO_INSTRUMENTS, as_of)
    sectors = _quote_group(SECTOR_INDICES, as_of) if include_sectors else []

    header = "## Indian market context"
    if as_of:
        header += f" (as of {as_of})"

    blocks = [
        header,
        "",
        _table("Broad indices", broad),
        _table("Volatility", vix),
    ]
    if sectors:
        blocks.append(_table("Sector indices", sectors))
    blocks.append(_table("Currency, commodities and global rates", macro))

    blocks.append(
        "*Nifty 50 is the alpha benchmark for NSE listings and the Sensex for "
        "BSE listings. The rupee, crude, gold, US 10-year yield and the dollar "
        "index are included because they drive FII flows and input costs for "
        "Indian companies.*\n"
    )
    return "\n".join(blocks)


def get_sector_snapshot(sector: str, as_of: Optional[str] = None) -> str:
    """One sector index's move, for pairing with that sector's news."""
    symbol = SECTOR_INDICES.get(sector)
    if not symbol:
        return ""
    q = _quote(sector, symbol, as_of)
    if not q.ok:
        return f"{sector} index: not available."
    return (
        f"{sector} index ({q.symbol}): {q.last:,.2f} "
        f"({q.change_1d:+.2f}% 1D, {q.change_5d:+.2f}% 1W, {q.change_1m:+.2f}% 1M)"
        if q.change_1m is not None
        else f"{sector} index ({q.symbol}): {q.last:,.2f}"
    )
