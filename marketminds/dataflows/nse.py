"""NSE corporate announcements — official filings, best-effort.

Company disclosures to the exchange (board meetings, order wins, results
intimations, pledge and promoter-holding changes) are the highest-signal
Indian source there is: they are the primary document, filed before the press
writes about it.

NSE publishes no documented public API. The endpoint used here is the one the
nseindia.com site calls for its own announcements page, which means:

- It is undocumented and can change or disappear without notice.
- It rejects clients that do not look like a browser, and often refuses
  requests from datacentre IP ranges — including, typically, cloud hosts and
  Docker containers on cloud VMs.

So this module is written to fail quietly and never block a run. When the
endpoint is unreachable the analyst simply proceeds on news and fundamentals,
with a note saying filings were unavailable rather than a silent gap.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

logger = logging.getLogger(__name__)

_BASE = "https://www.nseindia.com"
_ANNOUNCEMENTS = f"{_BASE}/api/corporate-announcements?index=equities"
_TIMEOUT = 12.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{_BASE}/companies-listing/corporate-filings-announcements",
    "Connection": "keep-alive",
}


def _fetch_json(url: str) -> Optional[object]:
    """GET JSON from NSE, carrying cookies as the site expects.

    NSE sets a session cookie on the landing page and requires it on the API
    call; an opener with a cookie jar reproduces that in two requests.
    """
    try:
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        # Prime the session. A failure here is not fatal — the API sometimes
        # answers without it.
        try:
            opener.open(Request(_BASE, headers=_HEADERS), timeout=_TIMEOUT).read()
        except Exception:
            pass

        with opener.open(Request(url, headers=_HEADERS), timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        logger.info("NSE endpoint unavailable: %s", exc)
        return None


def _rows(payload) -> List[dict]:
    """NSE returns either a bare list or wraps it under a data key."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "rows", "announcements"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def _parse_dt(raw: str) -> Optional[datetime]:
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def get_corporate_announcements(
    symbol: str,
    look_back_days: int = 30,
    limit: int = 15,
) -> str:
    """Recent exchange filings for one NSE symbol, as a markdown block.

    ``symbol`` may carry the ``.NS`` suffix; NSE indexes by the bare name.
    """
    base = symbol.split(".")[0].upper()

    payload = _fetch_json(_ANNOUNCEMENTS)
    if payload is None:
        return (
            "## NSE corporate filings\n\n"
            "*NSE's announcements endpoint was unreachable for this run "
            "(it is undocumented and blocks many non-browser clients). "
            "Treat filings as unchecked rather than absent.*\n"
        )

    cutoff = datetime.now() - timedelta(days=look_back_days)
    matches = []

    for row in _rows(payload):
        row_symbol = str(row.get("symbol") or row.get("sm_symbol") or "").upper()
        if row_symbol != base:
            continue

        when = _parse_dt(str(row.get("an_dt") or row.get("sort_date") or ""))
        if when and when < cutoff:
            continue

        subject = (
            row.get("desc")
            or row.get("subject")
            or row.get("attchmntText")
            or row.get("smIndustry")
            or ""
        )
        detail = (row.get("attchmntText") or row.get("more") or "").strip()
        matches.append((when, str(subject).strip(), detail[:300]))
        if len(matches) >= limit:
            break

    if not matches:
        return (
            f"## NSE corporate filings\n\n"
            f"No filings by {base} in the last {look_back_days} days "
            f"appeared in the exchange's current announcements feed.\n"
        )

    lines = [f"## NSE corporate filings — {base} (last {look_back_days} days)", ""]
    for when, subject, detail in matches:
        stamp = when.strftime("%Y-%m-%d %H:%M") if when else "undated"
        lines.append(f"- **{stamp}** — {subject}")
        if detail:
            lines.append(f"  {detail}")
    lines.append("")
    return "\n".join(lines)
