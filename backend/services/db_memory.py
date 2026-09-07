"""Database-backed trading decision log.

The agent library writes its decision log to a markdown file, which is right
for the CLI. A deployed instance cannot rely on that: the container's disk is
ephemeral, and the decision log is the one piece of state whose loss actually
degrades later analyses — the Portfolio Manager reads past calls and their
outcomes out of it.

This class presents the same interface as
:class:`marketminds.agents.utils.memory.TradingMemoryLog` and stores entries as
rows instead. ``MarketMindsGraph`` takes whichever it is handed, so neither the
graph nor the agents know the difference.

**Reads are shared, writes are private.** Every run learns from every entry in
the table, so a new user benefits from the pool immediately; but each entry
records who created it, and the Memory page shows a user only their own. The
consequence worth stating plainly: another user's reasoning can still surface
inside a generated report, because it fed the prompt. It is the history that
is private, not its influence.

Each operation opens its own short-lived session. A run occupies a background
thread for several minutes, and holding one session open across that would pin
a pooled connection for the whole analysis.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional

from backend.models import MemoryLogEntry
from marketminds.agents.utils.memory_format import select_past_context
from marketminds.agents.utils.rating import parse_rating

logger = logging.getLogger(__name__)


def _fmt_pct(value: Optional[float]) -> Optional[str]:
    """Render a return as the log's display form, e.g. ``+3.2%``."""
    return None if value is None else f"{value:+.1%}"


def _fmt_days(value: Optional[int]) -> Optional[str]:
    return None if value is None else f"{value}d"


def _to_entry(row: MemoryLogEntry) -> dict:
    """Convert a row into the dict shape the formatters and agents expect."""
    pending = row.resolved_at is None
    return {
        "id": row.id,
        "user_id": row.user_id,
        "date": row.trade_date,
        "ticker": row.ticker,
        "rating": row.rating,
        "pending": pending,
        "raw": None if pending else _fmt_pct(row.raw_return),
        "alpha": None if pending else _fmt_pct(row.alpha_return),
        "holding": None if pending else _fmt_days(row.holding_days),
        "decision": row.decision or "",
        "reflection": row.reflection or "",
        # Numeric forms, for callers that want the values rather than the tag
        # text — the API layer would otherwise parse the strings straight back.
        "raw_return": row.raw_return,
        "alpha_return": row.alpha_return,
        "holding_days": row.holding_days,
        "created_at": row.created_at,
    }


class DatabaseMemoryLog:
    """Decision log stored in the database rather than a markdown file."""

    def __init__(self, session_factory, user_id: Optional[str] = None,
                 max_entries: Optional[int] = None):
        self._session_factory = session_factory
        self._user_id = user_id
        self._max_entries = max_entries

    @contextmanager
    def _session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    # --- Write path -------------------------------------------------------

    def store_decision(self, ticker: str, trade_date: str,
                       final_trade_decision: str) -> None:
        """Record a decision as pending, to be resolved on a later run."""
        # Never log a decision with no text behind it. `parse_rating` falls
        # back to "Hold" for unparseable input, so an empty Portfolio Manager
        # output would be filed as a real Hold and then fed to a later run as
        # prior experience. A gap in the record is recoverable; an invented
        # past call is not.
        if not str(final_trade_decision or "").strip():
            logger.warning(
                "Refusing to log an empty decision for %s on %s — the Portfolio "
                "Manager produced no output, so there is no rating to record.",
                ticker, trade_date,
            )
            return

        with self._session() as session:
            existing = (
                session.query(MemoryLogEntry)
                .filter(
                    MemoryLogEntry.ticker == ticker,
                    MemoryLogEntry.trade_date == trade_date,
                    MemoryLogEntry.resolved_at.is_(None),
                )
                .first()
            )
            if existing is not None:
                return  # already pending for this ticker and date

            session.add(MemoryLogEntry(
                user_id=self._user_id,
                ticker=ticker,
                trade_date=trade_date,
                rating=parse_rating(final_trade_decision),
                decision=final_trade_decision,
            ))
            session.commit()

    # --- Read path --------------------------------------------------------

    def load_entries(self) -> List[dict]:
        """Every entry in the pool, oldest first.

        Deliberately unscoped: the shared pool is what every run learns from.
        The Memory page scopes to one user itself.
        """
        with self._session() as session:
            rows = (
                session.query(MemoryLogEntry)
                .order_by(MemoryLogEntry.id.asc())
                .all()
            )
            return [_to_entry(row) for row in rows]

    def get_pending_entries(self) -> List[dict]:
        with self._session() as session:
            rows = (
                session.query(MemoryLogEntry)
                .filter(MemoryLogEntry.resolved_at.is_(None))
                .order_by(MemoryLogEntry.id.asc())
                .all()
            )
            return [_to_entry(row) for row in rows]

    def get_past_context(self, ticker: str, n_same: int = 5,
                         n_cross: int = 3) -> str:
        """Past-experience block for the agent prompt.

        Shares its implementation with the file-backed log, so the same
        history produces the same prompt either way.
        """
        return select_past_context(self.load_entries(), ticker, n_same, n_cross)

    # --- Update path ------------------------------------------------------

    def update_with_outcome(self, ticker: str, trade_date: str,
                            raw_return: float, alpha_return: float,
                            holding_days: int, reflection: str) -> None:
        self.batch_update_with_outcomes([{
            "ticker": ticker,
            "trade_date": trade_date,
            "raw_return": raw_return,
            "alpha_return": alpha_return,
            "holding_days": holding_days,
            "reflection": reflection,
        }])

    def batch_update_with_outcomes(self, updates: List[dict]) -> None:
        """Resolve pending entries with their realised outcomes.

        Applied in one transaction: an outcome and its reflection describe the
        same entry, and a half-written pair would be read by a later run as a
        resolved call with no lesson attached.
        """
        if not updates:
            return

        with self._session() as session:
            resolved_any = False
            for update in updates:
                row = (
                    session.query(MemoryLogEntry)
                    .filter(
                        MemoryLogEntry.ticker == update["ticker"],
                        MemoryLogEntry.trade_date == update["trade_date"],
                        MemoryLogEntry.resolved_at.is_(None),
                    )
                    .order_by(MemoryLogEntry.id.asc())
                    .first()
                )
                if row is None:
                    continue
                row.raw_return = update["raw_return"]
                row.alpha_return = update["alpha_return"]
                row.holding_days = update["holding_days"]
                row.reflection = update["reflection"]
                row.resolved_at = datetime.now(timezone.utc)
                resolved_any = True

            if not resolved_any:
                return

            self._prune(session)
            session.commit()

    # --- Rotation ---------------------------------------------------------

    def _prune(self, session) -> None:
        """Drop the oldest resolved entries once past the cap.

        Pending entries are never dropped — they are unfinished work, and
        losing one means its outcome is never recorded at all.
        """
        if not self._max_entries or self._max_entries <= 0:
            return

        resolved = (
            session.query(MemoryLogEntry)
            .filter(MemoryLogEntry.resolved_at.isnot(None))
            .order_by(MemoryLogEntry.id.asc())
            .all()
        )
        excess = len(resolved) - self._max_entries
        for row in resolved[:max(excess, 0)]:
            session.delete(row)
