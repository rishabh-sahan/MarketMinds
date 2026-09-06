"""Indian market domain rules — exchanges, tickers, indices, and the calendar.

MarketMinds analyses Indian listings only. Everything that encodes "which
market are we in" lives here so the rest of the codebase never has to guess:
which exchange suffix a symbol needs, which index it is measured against,
what a sector's benchmark is, and whether a given date was actually a
trading session.

Yahoo Finance is the price source, and it will not return data for a bare
NSE name — ``RELIANCE`` yields nothing while ``RELIANCE.NS`` yields a full
series. Worse, the indicator path degrades to a well-formed report with
blank values rather than an error, so an unqualified ticker produces
confident analysis of nothing. :func:`resolve_ticker` closes that hole.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exchanges
# ---------------------------------------------------------------------------

NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"
INDIAN_SUFFIXES = (NSE_SUFFIX, BSE_SUFFIX)

EXCHANGE_NAMES = {
    NSE_SUFFIX: "NSE",
    BSE_SUFFIX: "BSE",
}

# Suffixes belonging to other markets. Rejected with a specific message so a
# user pasting a US or Tokyo ticker learns why instead of seeing "no data".
FOREIGN_SUFFIXES = {
    ".T": "Tokyo", ".HK": "Hong Kong", ".L": "London", ".TO": "Toronto",
    ".AX": "Australia", ".SI": "Singapore", ".KS": "Korea", ".SS": "Shanghai",
    ".SZ": "Shenzhen", ".PA": "Paris", ".DE": "Germany", ".MI": "Milan",
    ".AS": "Amsterdam", ".SW": "Switzerland", ".MX": "Mexico", ".SA": "Brazil",
}

IST = ZoneInfo("Asia/Kolkata")
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "₹"

# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------

NIFTY_50 = "^NSEI"
SENSEX = "^BSESN"
NIFTY_BANK = "^NSEBANK"
INDIA_VIX = "^INDIAVIX"

# Alpha benchmark per exchange. NSE listings are measured against the Nifty 50,
# BSE listings against the Sensex.
BENCHMARK_BY_SUFFIX = {
    NSE_SUFFIX: NIFTY_50,
    BSE_SUFFIX: SENSEX,
}

DEFAULT_BENCHMARK = NIFTY_50

# Broad-market and sector indices, all verified against Yahoo Finance.
BROAD_INDICES = {
    "Nifty 50": NIFTY_50,
    "Sensex": SENSEX,
    "Nifty Bank": NIFTY_BANK,
    "Nifty Next 50": "^NSMIDCP",
    "Nifty Midcap 50": "^NSEMDCP50",
    "Nifty 500": "^CRSLDX",
    # Nifty Smallcap 100 is deliberately absent: the price source exposes no
    # usable history for it, so including it only ever produced an empty row.
}

SECTOR_INDICES = {
    "IT": "^CNXIT",
    "Auto": "^CNXAUTO",
    "Pharma": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY",
    "PSU Bank": "^CNXPSUBANK",
    "Infrastructure": "^CNXINFRA",
    "Financial Services": "NIFTY_FIN_SERVICE.NS",
}

# Global instruments that move Indian equities: the rupee, crude (India imports
# most of its oil), gold (a competing retail asset and a reserve line), US
# yields and the dollar index (both drive FII flows).
MACRO_INSTRUMENTS = {
    "USD/INR": "USDINR=X",
    "Brent Crude": "BZ=F",
    "Gold": "GC=F",
    "US 10Y Yield": "^TNX",
    "Dollar Index": "DX-Y.NYB",
}

VOLATILITY_INDEX = {"India VIX": INDIA_VIX}


class NotAnIndianTickerError(ValueError):
    """Raised when a symbol cannot be resolved to an NSE or BSE listing."""


@dataclass(frozen=True)
class ResolvedTicker:
    """A symbol confirmed to have price data on an Indian exchange."""

    symbol: str          # exchange-qualified, e.g. "RELIANCE.NS"
    base: str            # bare name, e.g. "RELIANCE"
    suffix: str          # ".NS" or ".BO"

    @property
    def exchange(self) -> str:
        return EXCHANGE_NAMES.get(self.suffix, "NSE")

    @property
    def benchmark(self) -> str:
        return BENCHMARK_BY_SUFFIX.get(self.suffix, DEFAULT_BENCHMARK)

    def __str__(self) -> str:
        return self.symbol


def split_suffix(symbol: str) -> Tuple[str, Optional[str]]:
    """Split ``RELIANCE.NS`` into ``("RELIANCE", ".NS")``."""
    upper = symbol.strip().upper()
    for suffix in INDIAN_SUFFIXES:
        if upper.endswith(suffix):
            return upper[: -len(suffix)], suffix
    for suffix in FOREIGN_SUFFIXES:
        if upper.endswith(suffix):
            return upper[: -len(suffix)], suffix
    return upper, None


def _has_price_data(symbol: str) -> bool:
    """Whether Yahoo Finance returns any recent candles for ``symbol``."""
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="1mo")
        return hist is not None and not hist.empty
    except Exception as exc:  # network, parse, or upstream failure
        logger.warning("Price-data probe failed for %s: %s", symbol, exc)
        return False


@lru_cache(maxsize=512)
def resolve_ticker(raw: str) -> ResolvedTicker:
    """Resolve user input to an exchange-qualified Indian ticker.

    Rules, in order:

    - An explicit ``.NS`` / ``.BO`` suffix is respected as given.
    - A suffix from another market is rejected outright.
    - An all-numeric input is rejected: it is a BSE scrip code, which the
      price source does not key on.
    - Anything else is tried on NSE first, then BSE.

    Resolution is verified against real price data rather than assumed, so a
    misspelled name fails immediately instead of producing an empty report.
    Results are cached because a single run resolves the same ticker many
    times across agents and tools.
    """
    if not raw or not raw.strip():
        raise NotAnIndianTickerError("No ticker supplied.")

    base, suffix = split_suffix(raw)

    if suffix in FOREIGN_SUFFIXES:
        market = FOREIGN_SUFFIXES[suffix]
        raise NotAnIndianTickerError(
            f"'{raw.strip()}' is a {market} listing. MarketMinds analyses Indian "
            f"equities only — use an NSE ('{base}.NS') or BSE ('{base}.BO') symbol."
        )

    if not base:
        raise NotAnIndianTickerError(f"'{raw.strip()}' is not a usable ticker.")

    if base.isdigit():
        # BSE identifies scrips by numeric code, but the price source keys BSE
        # listings by name (RELIANCE.BO), so a code resolves to nothing.
        raise NotAnIndianTickerError(
            f"'{base}' looks like a BSE scrip code. Use the trading symbol "
            f"instead — for example 'RELIANCE' or 'RELIANCE.BO'."
        )

    # An explicit Indian suffix is honoured, but still verified. Otherwise NSE
    # is tried first: it lists nearly every actively traded name, and the
    # price source's BSE coverage is partial.
    candidates = [suffix] if suffix in INDIAN_SUFFIXES else [NSE_SUFFIX, BSE_SUFFIX]

    for candidate in candidates:
        symbol = f"{base}{candidate}"
        if _has_price_data(symbol):
            return ResolvedTicker(symbol=symbol, base=base, suffix=candidate)

    tried = ", ".join(f"{base}{c}" for c in candidates)
    raise NotAnIndianTickerError(
        f"No price data found for '{raw.strip()}' on NSE or BSE (tried {tried}). "
        "Check the symbol — MarketMinds covers Indian listings only."
    )


def benchmark_for(symbol: str) -> str:
    """Alpha benchmark for a symbol, without requiring a network round-trip."""
    _, suffix = split_suffix(symbol)
    return BENCHMARK_BY_SUFFIX.get(suffix, DEFAULT_BENCHMARK)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def now_ist() -> datetime:
    """Current time in Indian Standard Time."""
    return datetime.now(IST)


def today_ist() -> date:
    """Today's date in IST — the market's day, not the host's."""
    return now_ist().date()


@lru_cache(maxsize=8)
def _nifty_sessions(year: int) -> frozenset:
    """Dates on which the Nifty 50 actually traded in ``year``.

    Derived from index history rather than a hardcoded holiday table, so it
    stays correct as exchange holidays change year to year and needs no
    annual maintenance.
    """
    try:
        import yfinance as yf

        hist = yf.Ticker(NIFTY_50).history(
            start=f"{year}-01-01", end=f"{year + 1}-01-01"
        )
        if hist is None or hist.empty:
            return frozenset()
        return frozenset(d.date() for d in hist.index)
    except Exception as exc:
        logger.warning("Could not load NSE sessions for %s: %s", year, exc)
        return frozenset()


def is_trading_day(day: date | str) -> bool:
    """Whether ``day`` was an NSE trading session.

    Falls back to a weekday check when index history is unavailable (offline,
    or a date in the future), which is the safe direction: it never rejects a
    date the exchange might have been open.
    """
    if isinstance(day, str):
        day = datetime.strptime(day, "%Y-%m-%d").date()

    if day.weekday() >= 5:  # Saturday, Sunday
        return False

    sessions = _nifty_sessions(day.year)
    if not sessions:
        return True  # cannot verify; do not block the run
    if day > max(sessions):
        return True  # beyond available history
    return day in sessions


def previous_trading_day(day: date | str) -> date:
    """The most recent NSE session on or before ``day``."""
    if isinstance(day, str):
        day = datetime.strptime(day, "%Y-%m-%d").date()
    probe = day
    for _ in range(15):  # longest Indian market break is well under this
        if is_trading_day(probe):
            return probe
        probe -= timedelta(days=1)
    return day


def describe_session(day: date | str) -> str:
    """Human-readable note about a date, for prompts and validation messages."""
    if isinstance(day, str):
        day = datetime.strptime(day, "%Y-%m-%d").date()
    if is_trading_day(day):
        return f"{day.isoformat()} was an NSE trading session."
    prev = previous_trading_day(day)
    reason = "a weekend" if day.weekday() >= 5 else "an exchange holiday"
    return (
        f"{day.isoformat()} was not a trading day ({reason}); "
        f"the most recent session was {prev.isoformat()}."
    )


def format_inr(value: float) -> str:
    """Format a number as rupees using the Indian digit grouping (lakh/crore).

    ``1234567.5`` becomes ``₹12,34,567.50`` — the last three digits group
    together and every pair groups above that.
    """
    if value is None:
        return "n/a"
    negative = value < 0
    whole, _, frac = f"{abs(value):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{'-' if negative else ''}{CURRENCY_SYMBOL}{whole}.{frac}"
