"""News and disclosure tools, sourced for the Indian market.

Yahoo Finance carries Indian listings but its per-ticker news feed for them is
thin and frequently unrelated. Every tool here therefore pairs the vendor feed
with Indian coverage — Google News (India edition) and the major domestic
financial outlets — plus, where relevant, exchange filings and the live index
backdrop.
"""

import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from marketminds.dataflows.interface import route_to_vendor

logger = logging.getLogger(__name__)


def _company_name(ticker: str) -> str:
    """Best-effort company name, used to search Indian media by name.

    Headlines say "Reliance Industries", not "RELIANCE.NS", so searching by
    symbol alone misses most domestic coverage.
    """
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        name = info.get("longName") or info.get("shortName") or ""
        # Trim the corporate-form suffixes that make headline matching brittle.
        for tail in (" Limited", " Ltd.", " Ltd", " Corporation", " Corp."):
            if name.endswith(tail):
                name = name[: -len(tail)]
        return name.strip()
    except Exception as exc:
        logger.info("Company-name lookup failed for %s: %s", ticker, exc)
        return ""


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news for an Indian listed company.

    Combines the configured news vendor with Indian media coverage (Google
    News India edition plus domestic financial outlets), searched by company
    name as well as symbol.

    Args:
        ticker (str): Ticker symbol, e.g. RELIANCE.NS
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format

    Returns:
        str: Formatted news from both vendor and Indian sources
    """
    from marketminds.dataflows.india_news import get_india_ticker_news

    blocks = []

    try:
        vendor = route_to_vendor("get_news", ticker, start_date, end_date)
        if vendor and vendor.strip():
            blocks.append(vendor)
    except Exception as exc:
        logger.info("Vendor news failed for %s: %s", ticker, exc)

    try:
        blocks.append(
            get_india_ticker_news(
                ticker=ticker,
                company_name=_company_name(ticker),
                start_date=start_date,
                end_date=end_date,
            )
        )
    except Exception as exc:
        logger.warning("Indian ticker news failed for %s: %s", ticker, exc)

    return "\n\n".join(blocks) if blocks else f"No news found for {ticker}"


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[Optional[int], "Days to look back; omit to use the configured default"] = None,
    limit: Annotated[Optional[int], "Max articles to return; omit to use the configured default"] = None,
) -> str:
    """
    Retrieve the macro and policy backdrop for Indian markets.

    Covers RBI policy and liquidity, SEBI and regulation, government policy
    and the Budget, inflation and growth prints, GST and tax collections,
    FII/DII flows, the rupee and reserves, index-inclusion events (MSCI,
    FTSE), IPO activity and mutual-fund flows — plus sector news and the live
    index, currency and commodity backdrop.

    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Days to look back; omit to inherit config
        limit (int): Retained for interface compatibility; unused

    Returns:
        str: A formatted macro, sector and market-context brief
    """
    from marketminds.dataflows.config import get_config
    from marketminds.dataflows.india_market import get_market_context
    from marketminds.dataflows.india_news import (
        MACRO_TOPICS,
        SECTOR_TOPICS,
        get_india_macro_news,
        get_india_sector_news,
        get_indian_market_headlines,
    )

    config = get_config()
    days = look_back_days or config.get("global_news_lookback_days", 7)

    chosen_macro = config.get("macro_news_topics") or []
    topics = {k: v for k, v in MACRO_TOPICS.items() if k in chosen_macro} or MACRO_TOPICS
    chosen_sectors = config.get("sector_news_topics") or list(SECTOR_TOPICS)

    blocks = []

    if config.get("include_market_context", True):
        try:
            blocks.append(get_market_context(as_of=curr_date))
        except Exception as exc:
            logger.warning("Market context failed: %s", exc)

    for label, fetch in (
        ("macro", lambda: get_india_macro_news(curr_date, look_back_days=days, topics=topics)),
        ("sector", lambda: get_india_sector_news(sectors=chosen_sectors, look_back_days=days)),
        ("headlines", lambda: get_indian_market_headlines(look_back_days=min(days, 3))),
    ):
        try:
            out = fetch()
            if out and out.strip():
                blocks.append(out)
        except Exception as exc:
            logger.warning("Indian %s news failed: %s", label, exc)

    if not blocks:
        # Fall back to the vendor feed rather than returning nothing at all.
        try:
            return route_to_vendor("get_global_news", curr_date, look_back_days, limit)
        except Exception:
            return "No macro news could be retrieved for this window."

    return "\n\n".join(blocks)


@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider and promoter activity plus exchange filings.

    For Indian listings this pairs the vendor's insider-transaction feed
    (sparse for NSE names) with corporate announcements filed to the
    exchange — board meetings, results intimations, order wins, and promoter
    pledge or holding changes.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A report of insider activity and exchange filings
    """
    from marketminds.dataflows.nse import get_corporate_announcements

    blocks = []

    try:
        vendor = route_to_vendor("get_insider_transactions", ticker)
        if vendor and vendor.strip():
            blocks.append(vendor)
    except Exception as exc:
        logger.info("Vendor insider data failed for %s: %s", ticker, exc)

    try:
        blocks.append(get_corporate_announcements(ticker))
    except Exception as exc:
        logger.warning("NSE filings failed for %s: %s", ticker, exc)

    return "\n\n".join(blocks) if blocks else f"No insider or filing data found for {ticker}"


@tool
def get_market_context(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve the live Indian market backdrop for a date.

    Nifty 50, Sensex, Bank Nifty and broad indices; India VIX; every sector
    index; and the global inputs Indian equities react to — USD/INR, Brent
    crude, gold, the US 10-year yield and the dollar index. Each with 1-day,
    1-week and 1-month moves.

    Args:
        curr_date (str): Current date in yyyy-mm-dd format

    Returns:
        str: A markdown snapshot of indices, sectors, currency and commodities
    """
    from marketminds.dataflows.india_market import get_market_context as _context

    try:
        return _context(as_of=curr_date)
    except Exception as exc:
        logger.warning("Market context failed: %s", exc)
        return "Market context is unavailable for this run."
