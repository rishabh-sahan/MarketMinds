"""Indian financial news aggregation from free, key-less sources.

Yahoo Finance carries Indian tickers but its news feed for them is thin and
frequently off-target — a query for ``TCS.NS`` returns unrelated US small-cap
earnings calls. This module supplies the Indian coverage the analysts actually
need, from two kinds of source:

* **Google News RSS**, India edition. Query-driven, so it serves ticker news,
  macro themes (RBI, SEBI, GST, inflation, FII/DII flows, MSCI rejigs) and
  sector coverage through one mechanism. Supports ``when:7d`` style recency
  operators.
* **Indian outlet RSS feeds** — Economic Times, Moneycontrol, Livemint,
  Business Standard and Hindu BusinessLine. Broad market and economy coverage
  that is not tied to a search phrase.

Every fetch degrades to an empty list rather than raising, so a single dead
feed never fails a run. All sources are free and need no API key.

Feeds that were evaluated and deliberately excluded: NDTV Profit and Zeebiz
(both return HTTP 403 to non-browser clients), Financial Express (serves HTML,
not RSS at its feed URL), and YouTube channel feeds (titles only, no
transcript, and hardcoded channel ids rot silently).
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable, List, Optional, Sequence
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 12.0

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

# Verified reachable and returning items. Keyed by the label shown to agents.
OUTLET_FEEDS = {
    "Economic Times · Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times · Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Economic Times · Economy": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "Moneycontrol · Business": "https://www.moneycontrol.com/rss/business.xml",
    "Moneycontrol · Markets": "https://www.moneycontrol.com/rss/marketreports.xml",
    "Moneycontrol · Results": "https://www.moneycontrol.com/rss/results.xml",
    "Livemint · Markets": "https://www.livemint.com/rss/markets",
    "Livemint · Companies": "https://www.livemint.com/rss/companies",
    "Business Standard · Markets": "https://www.business-standard.com/rss/markets-106.rss",
    "Hindu BusinessLine · Markets": "https://www.thehindubusinessline.com/markets/feeder/default.rss",
}

# Macro themes that move Indian equities. Each becomes one Google News query.
MACRO_TOPICS = {
    "Monetary policy": "RBI monetary policy repo rate liquidity",
    "Regulation": "SEBI regulation markets circular",
    "Government policy": "India government policy budget reform stocks impact",
    "Inflation": "India CPI WPI inflation data",
    "Growth": "India GDP growth IIP core sector data",
    "Tax collections": "India GST collections direct tax revenue",
    "Institutional flows": "FII DII flows Indian equities buying selling",
    "Currency and reserves": "rupee USDINR RBI forex reserves gold reserves",
    "Index inclusion": "MSCI FTSE index India rejig inclusion weightage",
    "Global spillovers": "global markets geopolitics crude oil impact Indian markets",
    "Primary market": "India IPO listing mainboard subscription",
    "Fund flows": "India mutual fund SIP inflows equity schemes",
}

# Sector coverage. Keys match the sector index labels in `india.SECTOR_INDICES`
# where they overlap, so a sector view can pair news with its index move.
SECTOR_TOPICS = {
    "IT": "Indian IT services sector TCS Infosys deal wins outlook",
    "Banking": "India banking sector credit growth NPA RBI norms",
    "Financial Services": "India NBFC fintech lending regulation",
    "Pharma": "India pharma sector USFDA approvals exports",
    "Auto": "India auto sales monthly EV two-wheeler passenger vehicle",
    "FMCG": "India FMCG demand rural consumption volume growth",
    "Metal": "India metal steel aluminium prices demand",
    "Energy": "India energy oil gas refining renewable capacity",
    "Realty": "India real estate housing sales launches",
    "Infrastructure": "India infrastructure capex roads railways order book",
    "Healthcare": "India hospital healthcare sector expansion",
    "New-age tech": "India startup new-age tech listed companies profitability",
}


@dataclass
class Article:
    """One normalised news item from any source."""

    title: str
    link: str
    published: Optional[datetime]
    source: str
    summary: str = ""

    def key(self) -> str:
        """Dedupe key — headlines repeat verbatim across syndicating outlets."""
        return re.sub(r"[^a-z0-9]+", "", self.title.lower())[:90]


# ---------------------------------------------------------------------------
# Fetch and parse
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: float = _TIMEOUT) -> Optional[str]:
    """GET a URL, returning None on any failure."""
    try:
        req = Request(url, headers={"User-Agent": _UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.info("Feed unavailable (%s): %s", url.split("/")[2], exc)
        return None


def _text(node, *names: str) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse RFC-822 (RSS) or ISO-8601 (Atom) timestamps as UTC-aware."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 320) -> str:
    """Strip markup and collapse whitespace in a feed summary."""
    text = _TAG_RE.sub(" ", text or "")
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _parse_feed(xml: str, source: str) -> List[Article]:
    """Parse an RSS or Atom document into articles."""
    if not xml:
        return []
    try:
        root = ET.fromstring(xml.encode("utf-8", "replace"))
    except ET.ParseError as exc:
        logger.info("Malformed feed from %s: %s", source, exc)
        return []

    articles: List[Article] = []

    # RSS 2.0
    for item in root.iter("item"):
        title = _text(item, "title")
        if not title:
            continue
        articles.append(
            Article(
                title=re.sub(r"\s+", " ", title).strip(),
                link=_text(item, "link"),
                published=_parse_date(_text(item, "pubDate", "date")),
                source=source,
                summary=_clean(_text(item, "description")),
            )
        )

    # Atom
    atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{atom}entry"):
        title_el = entry.find(f"{atom}title")
        if title_el is None or not title_el.text:
            continue
        link_el = entry.find(f"{atom}link")
        summary_el = entry.find(f"{atom}summary") or entry.find(f"{atom}content")
        published_el = entry.find(f"{atom}published") or entry.find(f"{atom}updated")
        articles.append(
            Article(
                title=re.sub(r"\s+", " ", title_el.text).strip(),
                link=(link_el.get("href") if link_el is not None else "") or "",
                published=_parse_date(published_el.text if published_el is not None else ""),
                source=source,
                summary=_clean(summary_el.text if summary_el is not None else ""),
            )
        )

    return articles


def _fetch_many(jobs: Sequence[tuple]) -> List[Article]:
    """Fetch several feeds concurrently. ``jobs`` is a list of (label, url)."""
    if not jobs:
        return []

    def one(job):
        label, url = job
        return _parse_feed(_fetch(url) or "", label)

    # Modest pool: these are small documents and the sources are unrelated
    # hosts, so parallelism turns a dozen sequential round-trips into one wait.
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        results = list(pool.map(one, jobs))

    return [article for batch in results for article in batch]


# ---------------------------------------------------------------------------
# Public fetchers
# ---------------------------------------------------------------------------

def google_news(query: str, within_days: int = 7) -> List[Article]:
    """Search Google News (India edition) for ``query``."""
    scoped = f"{query} when:{max(1, within_days)}d"
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(scoped))
    return _parse_feed(_fetch(url) or "", "Google News")


def _filter_and_rank(
    articles: Iterable[Article],
    start: Optional[datetime],
    end: Optional[datetime],
    limit: int,
    must_match: Optional[Sequence[str]] = None,
) -> List[Article]:
    """Deduplicate, keep items in range, optionally require a keyword, sort."""
    seen = set()
    kept: List[Article] = []

    for article in articles:
        if not article.title:
            continue
        key = article.key()
        if key in seen:
            continue

        if article.published:
            if start and article.published < start:
                continue
            if end and article.published > end:
                continue

        if must_match:
            haystack = f"{article.title} {article.summary}".lower()
            if not any(term.lower() in haystack for term in must_match):
                continue

        seen.add(key)
        kept.append(article)

    # Undated items sort last rather than being dropped — some outlet feeds
    # omit pubDate but still carry current headlines.
    kept.sort(key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept[:limit]


def _render(heading: str, articles: Sequence[Article], empty_note: str) -> str:
    """Format articles as the markdown block agents read."""
    if not articles:
        return f"## {heading}\n\n{empty_note}\n"

    lines = [f"## {heading}", ""]
    for article in articles:
        when = article.published.astimezone(timezone.utc).strftime("%Y-%m-%d") if article.published else "undated"
        lines.append(f"### {article.title}")
        lines.append(f"*{article.source} · {when}*")
        if article.summary:
            lines.append("")
            lines.append(article.summary)
        lines.append("")
    return "\n".join(lines)


def get_india_ticker_news(
    ticker: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit: int = 20,
) -> str:
    """Indian-media news for one company.

    Searches Google News for the company by name and by symbol, then keeps
    only items that actually mention the company — a plain feed merge would
    otherwise flood the analyst with unrelated market chatter.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    window = max(1, (end - start).days)

    base = ticker.split(".")[0]
    terms = [t for t in {company_name, base} if t]

    queries = []
    if company_name:
        queries.append(f"{company_name} share price NSE")
        queries.append(f"{company_name} results order news")
    queries.append(f"{base} stock NSE India")

    articles: List[Article] = []
    for query in queries:
        articles.extend(google_news(query, within_days=window))

    kept = _filter_and_rank(articles, start, end, limit, must_match=terms)
    return _render(
        f"Indian media coverage — {company_name or base} ({start_date} to {end_date})",
        kept,
        "No Indian-media articles matched this company in the window.",
    )


def get_india_macro_news(
    end_date: str,
    look_back_days: int = 7,
    per_topic: int = 3,
    topics: Optional[dict] = None,
) -> str:
    """Macro and policy news across the themes that move Indian equities."""
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=look_back_days + 1)
    topics = topics or MACRO_TOPICS

    sections: List[str] = []
    jobs = [(label, query) for label, query in topics.items()]

    def one(job):
        label, query = job
        found = google_news(query, within_days=look_back_days)
        return label, _filter_and_rank(found, start, end, per_topic)

    with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
        for label, articles in pool.map(one, jobs):
            if not articles:
                continue
            lines = [f"### {label}"]
            for a in articles:
                when = a.published.strftime("%Y-%m-%d") if a.published else "undated"
                lines.append(f"- **{a.title}** ({a.source}, {when})")
                if a.summary:
                    lines.append(f"  {a.summary}")
            sections.append("\n".join(lines))

    if not sections:
        return "## Indian macro and policy news\n\nNo macro news retrieved for this window.\n"

    header = (
        f"## Indian macro and policy news "
        f"({(end - timedelta(days=look_back_days + 1)).date()} to {end_date})"
    )
    return header + "\n\n" + "\n\n".join(sections) + "\n"


def get_india_sector_news(
    sectors: Optional[Sequence[str]] = None,
    look_back_days: int = 7,
    per_sector: int = 3,
) -> str:
    """Sector-level news across the industries driving Indian markets."""
    chosen = {k: v for k, v in SECTOR_TOPICS.items() if not sectors or k in sectors}
    if not chosen:
        return ""

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=look_back_days + 1)

    def one(job):
        label, query = job
        return label, _filter_and_rank(google_news(query, within_days=look_back_days), start, end, per_sector)

    sections = []
    jobs = list(chosen.items())
    with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
        for label, articles in pool.map(one, jobs):
            if not articles:
                continue
            lines = [f"### {label}"]
            for a in articles:
                when = a.published.strftime("%Y-%m-%d") if a.published else "undated"
                lines.append(f"- **{a.title}** ({a.source}, {when})")
            sections.append("\n".join(lines))

    if not sections:
        return ""
    return "## Sector news\n\n" + "\n\n".join(sections) + "\n"


def get_indian_market_headlines(limit: int = 25, look_back_days: int = 3) -> str:
    """Front-page market and economy headlines from Indian outlets.

    Distinct from the topical searches above: this is what the Indian
    financial press is leading with right now, unfiltered by query.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=look_back_days + 1)
    articles = _fetch_many(list(OUTLET_FEEDS.items()))
    kept = _filter_and_rank(articles, start, end, limit)
    return _render(
        "Indian financial press — latest headlines",
        kept,
        "No headlines retrieved from Indian outlets.",
    )
