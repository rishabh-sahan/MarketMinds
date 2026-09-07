"""Shared formatting and selection logic for the decision log.

The decision log has two backing stores: a markdown file (used by the CLI and
by local runs) and database rows (used by the deployed web app, where the
container's disk does not survive a restart). Both must inject *identical*
text into the Portfolio Manager's prompt — a run's reasoning should not change
because of where its history happens to be kept.

So the selection and formatting live here, once, and both stores call in. The
stores differ only in how they load and persist entries.

An entry is a plain dict with the keys produced by either store:

    date       str   trade date, "YYYY-MM-DD"
    ticker     str
    rating     str   Buy / Hold / Sell
    pending    bool  True until the realised return is known
    raw        str   realised return, "+3.2%", or None while pending
    alpha      str   return against the benchmark, or None
    holding    str   holding period, "5d", or None
    decision   str   the Portfolio Manager's output
    reflection str   the lesson drawn once the outcome was known
"""

from __future__ import annotations

from typing import List, Sequence

# A cross-ticker lesson is quoted rather than summarised, so it needs a cap;
# the same call reads as noise past a few lines.
_CROSS_DECISION_CHARS = 300


def format_full(entry: dict) -> str:
    """Render one entry in full — tag, decision, and reflection if resolved."""
    raw = entry.get("raw") or "n/a"
    alpha = entry.get("alpha") or "n/a"
    holding = entry.get("holding") or "n/a"
    tag = (
        f"[{entry.get('date')} | {entry.get('ticker')} | {entry.get('rating')}"
        f" | {raw} | {alpha} | {holding}]"
    )
    parts = [tag, f"DECISION:\n{entry.get('decision') or ''}"]
    if entry.get("reflection"):
        parts.append(f"REFLECTION:\n{entry['reflection']}")
    return "\n\n".join(parts)


def format_reflection_only(entry: dict) -> str:
    """Render one entry compactly — the lesson, or a truncated decision.

    Used for other tickers, where the point is the transferable lesson rather
    than the full argument.
    """
    tag = (
        f"[{entry.get('date')} | {entry.get('ticker')} | {entry.get('rating')}"
        f" | {entry.get('raw') or 'n/a'}]"
    )
    if entry.get("reflection"):
        return f"{tag}\n{entry['reflection']}"
    decision = entry.get("decision") or ""
    text = decision[:_CROSS_DECISION_CHARS]
    suffix = "..." if len(decision) > _CROSS_DECISION_CHARS else ""
    return f"{tag}\n{text}{suffix}"


def select_past_context(
    entries: Sequence[dict],
    ticker: str,
    n_same: int = 5,
    n_cross: int = 3,
) -> str:
    """Build the past-experience block injected into the agent prompt.

    ``entries`` arrives oldest-first; the most recent are the most relevant,
    so selection walks backwards. Pending entries are excluded — an entry
    whose outcome is unknown carries no lesson yet, and including it would
    present an untested call as if it were experience.
    """
    resolved: List[dict] = [e for e in entries if not e.get("pending")]
    if not resolved:
        return ""

    same: List[dict] = []
    cross: List[dict] = []
    for entry in reversed(resolved):
        if len(same) >= n_same and len(cross) >= n_cross:
            break
        if entry.get("ticker") == ticker:
            if len(same) < n_same:
                same.append(entry)
        elif len(cross) < n_cross:
            cross.append(entry)

    if not same and not cross:
        return ""

    parts: List[str] = []
    if same:
        parts.append(f"Past analyses of {ticker} (most recent first):")
        parts.extend(format_full(e) for e in same)
    if cross:
        parts.append("Recent cross-ticker lessons:")
        parts.extend(format_reflection_only(e) for e in cross)
    return "\n\n".join(parts)
