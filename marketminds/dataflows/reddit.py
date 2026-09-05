"""Reddit search fetcher for ticker-specific discussion posts.

Reddit blocks all unauthenticated traffic to its JSON endpoints — every
request returns ``403 Blocked`` regardless of User-Agent. OAuth is therefore
mandatory, not optional.

Set up (one time):

1. Visit https://www.reddit.com/prefs/apps and create an app of type
   **script**. Any redirect URI works (e.g. ``http://localhost:8080``).
2. Copy the client ID (shown under the app name) and the secret.
3. Add to ``.env``::

       REDDIT_CLIENT_ID=your_client_id
       REDDIT_CLIENT_SECRET=your_client_secret
       REDDIT_USER_AGENT=python:marketminds:v0.2 (by /u/your_username)

``REDDIT_USER_AGENT`` is optional but recommended — Reddit asks for the
``platform:app_id:version (by /u/username)`` format and throttles generic
agents more aggressively.

Authentication uses the ``client_credentials`` grant, which yields an
app-only ("userless") token — sufficient for reading public subreddits and
requiring no Reddit password. The token is cached in-process until shortly
before it expires.

Authenticated clients get ~100 queries/minute, so a sweep across the full
subreddit list fits comfortably within one run's budget.

Every function degrades gracefully: on missing credentials, auth failure,
or network error it returns an explanatory string rather than raising, so
the calling agent always receives text it can reason about.
"""

from __future__ import annotations

import json
import logging
import os
import time
from base64 import b64encode
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API = "https://oauth.reddit.com/r/{sub}/search?{qs}"
_DEFAULT_UA = "python:marketminds:v0.2"

# Cached app-only token: (access_token, unix_expiry). Reddit tokens last
# ~24h; we refresh a minute early to avoid racing the boundary.
_token_cache: tuple[Optional[str], float] = (None, 0.0)
_TOKEN_REFRESH_MARGIN_SEC = 60

# Default subreddits ordered roughly by signal density for ticker-specific
# discussion. wallstreetbets has the most volume but most noise; stocks /
# investing trend more measured. Caller can override.
DEFAULT_SUBREDDITS = (
    "wallstreetbets",
    "stocks",
    "investing",
    "IndianStockMarket",
    "IndianStocks",
    "IndiaInvestments",
    "StockMarketIndia",
    "IndianStreetBets",
    "Indiastreetbets",
    "India_Investments",
    "IPO_India",
    "indianeconomy",
    "IndiaPulse",
    "IndiaGrowthStocks",
    "ShareBazarIndia",
    "IndiaFinance",
    "Indiantradingbets",
    "IndiaBusiness",
    "personalfinanceindia",
    "StockMarket",
    "EquityResearchIndia",
    "GoldIndia",
    "IndiaMoney",
)


def _user_agent() -> str:
    return os.environ.get("REDDIT_USER_AGENT") or _DEFAULT_UA


def _get_access_token(timeout: float = 10.0) -> Optional[str]:
    """Return a cached or freshly minted app-only OAuth token.

    Returns ``None`` when credentials are absent or the token request
    fails — callers treat that as "Reddit unavailable" rather than an error.
    """
    global _token_cache
    token, expiry = _token_cache
    if token and time.time() < expiry:
        return token

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    basic = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = Request(
        _TOKEN_URL,
        data=urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "User-Agent": _user_agent(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning("Reddit OAuth token request failed: %s", exc)
        return None

    token = payload.get("access_token")
    if not token:
        logger.warning("Reddit OAuth response contained no access_token")
        return None

    expires_in = payload.get("expires_in", 3600)
    _token_cache = (token, time.time() + expires_in - _TOKEN_REFRESH_MARGIN_SEC)
    return token


def _fetch_subreddit(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
    token: str,
) -> list[dict]:
    qs = urlencode({
        "q": ticker,
        "restrict_sr": "on",
        "sort": "new",
        "t": "week",  # last 7 days
        "limit": limit,
    })
    url = _API.format(sub=sub, qs=qs)
    req = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning("Reddit fetch failed for r/%s · %s: %s", sub, ticker, exc)
        return []
    children = (payload.get("data") or {}).get("children") or []
    return [c.get("data", {}) for c in children if isinstance(c, dict)]


def fetch_reddit_posts(
    ticker: str,
    subreddits: Iterable[str] = DEFAULT_SUBREDDITS,
    limit_per_sub: int = 5,
    timeout: float = 10.0,
    inter_request_delay: float = 0.15,
) -> str:
    """Fetch recent Reddit posts mentioning ``ticker`` across finance
    subreddits and return them as a formatted plaintext block.

    Requires ``REDDIT_CLIENT_ID`` / ``REDDIT_CLIENT_SECRET``; without them
    the function returns immediately with a setup hint instead of issuing
    requests that Reddit is guaranteed to reject.

    ``inter_request_delay`` paces the sweep under Reddit's ~100 req/min
    authenticated budget.
    """
    token = _get_access_token(timeout=timeout)
    if token is None:
        return (
            "<reddit unavailable: OAuth credentials not configured. Reddit blocks all "
            "unauthenticated API traffic. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET "
            "in .env (create a 'script' app at https://www.reddit.com/prefs/apps) to "
            "enable Reddit sentiment.>"
        )

    blocks = []
    total_posts = 0
    for i, sub in enumerate(subreddits):
        if i > 0:
            time.sleep(inter_request_delay)
        posts = _fetch_subreddit(ticker, sub, limit_per_sub, timeout, token)
        total_posts += len(posts)
        if not posts:
            blocks.append(f"r/{sub}: <no posts found mentioning {ticker.upper()} in the past 7 days>")
            continue

        lines = [f"r/{sub} — {len(posts)} recent posts mentioning {ticker.upper()}:"]
        for p in posts:
            title = (p.get("title") or "").replace("\n", " ").strip()
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            created = p.get("created_utc")
            created_str = (
                time.strftime("%Y-%m-%d", time.gmtime(created)) if created else "?"
            )
            selftext = (p.get("selftext") or "").replace("\n", " ").strip()
            if len(selftext) > 240:
                selftext = selftext[:240] + "…"
            lines.append(
                f"  [{created_str} · {score:>4}↑ · {comments:>3}c] {title}"
                + (f"\n    body excerpt: {selftext}" if selftext else "")
            )
        blocks.append("\n".join(lines))

    if total_posts == 0:
        return (
            f"<no Reddit posts found mentioning {ticker.upper()} across "
            f"{', '.join(f'r/{s}' for s in subreddits)} in the past 7 days>"
        )
    return "\n\n".join(blocks)
