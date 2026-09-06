"""Sentiment analyst — media sentiment for an Indian listed company.

A prompt that demands social-media analysis while only exposing a news tool
leads LLMs to fabricate forum and social content under prompt pressure. To
prevent that, this agent pre-fetches its sources before the LLM is invoked and
injects them into the prompt as structured blocks:

  1. Company news        — vendor feed plus Indian media (Google News India
                           edition, Economic Times, Moneycontrol, Mint,
                           Business Standard, Hindu BusinessLine)
  2. Indian market press — what the domestic financial press is leading with

Two social sources were evaluated and removed. StockTwits indexes US cashtags
and returns HTTP 404 for every NSE symbol. Reddit blocks all unauthenticated
API traffic, and its RSS endpoints rate-limit too aggressively to be a
dependable substitute — both contributed nothing but a placeholder for Indian
coverage. The report is therefore a media-sentiment read, and the prompt says
so rather than implying a retail-mood signal that was never measured.

The agent does not use tool-calling; the data is in the prompt from turn 0.
The LLM produces the sentiment report in a single invocation.
"""

from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from marketminds.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_news,
)
from marketminds.dataflows.india_news import get_indian_market_headlines


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches company news and the Indian market press, injects them into
    the prompt as structured blocks, and produces a sentiment report in a
    single LLM call.
    """

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = build_instrument_context(ticker)

        # Pre-fetch both sources. Each fetcher degrades gracefully and returns
        # a string (no exceptions surface from here), so the LLM always sees
        # something — either real data or a clear placeholder.
        news_block = get_news.func(ticker, start_date, end_date)
        press_block = get_indian_market_headlines(limit=15, look_back_days=3)

        system_message = _build_system_message(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            news_block=news_block,
            press_block=press_block,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # No bind_tools — the data is already in the prompt; a single LLM
        # call produces the report directly.
        chain = prompt | llm
        result = chain.invoke(state["messages"])

        return {
            "messages": [result],
            "sentiment_report": result.content,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    press_block: str,
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    return f"""You are a financial market sentiment analyst covering Indian equities. Your task is to produce a media sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on two complementary data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### Company news — vendor feed plus Indian media, past 7 days
Coverage of this specific company from Google News (India edition) and the domestic financial outlets. Fact-driven, institutional framing.

<start_of_news>
{news_block}
<end_of_news>

### Indian financial press — front-page market and economy headlines
What Economic Times, Moneycontrol, Mint, Business Standard and Hindu BusinessLine are leading with right now. This is the market-wide backdrop the company trades against, not company-specific news.

<start_of_press>
{press_block}
<end_of_press>

## Scope — read this before you write

These two blocks are the entirety of your evidence. You have **no retail or social-media data**: there is no cashtag-indexed feed for NSE symbols, and no forum data is collected. So this is a *media* sentiment read, not a retail-mood read.

Do not describe retail positioning, forum chatter, "what traders on social media are saying", or a bullish/bearish ratio. None of that was measured, and inventing it would misrepresent the confidence of everything downstream. Frame your conclusions as what the press coverage implies, and note the absence of retail data as a limitation of this report.

## How to analyze this data (best practices)

1. **Separate company signal from market backdrop.** The news block is about this company; the press block is about the market. A stock falling while the Nifty falls harder is relative strength, not weakness — say which is which.

2. **Look for cross-source divergences.** If company coverage is upbeat while the broader press is risk-off, that mismatch is itself a signal. Note when the two point opposite ways.

3. **Weigh the outlet and the framing.** A results-day report carries different weight from an opinion column or a re-syndicated wire story. Note when several outlets are all repeating one underlying source rather than reporting independently.

4. **Distinguish event from commentary.** A filing, an order win, a rating action or a results date is an event; an analyst's view or an editorial angle is commentary. Both are inputs, weighted very differently.

5. **Watch for the recurring narrative.** What theme keeps reappearing across the coverage? That is what is actually driving the story on this name.

6. **Be explicit about data limits.** If a block is thin, undated, or returned a placeholder, say so plainly and lower your stated confidence. A short honest report beats a padded one.

7. **Never invent coverage.** If a source returned nothing, report nothing from it. A fabricated headline or an imagined sentiment ratio is worse than an acknowledged gap.

8. **Identify catalysts and risks** surfaced by the coverage — results dates, order wins, regulatory or SEBI action, promoter or pledge changes, index-inclusion events, sector-wide moves.

9. **Past sentiment is not predictive.** Frame conclusions as one input for the trader alongside fundamentals and technicals, not as a price call.

## Output

Produce a sentiment report covering, in order:

1. **Overall media sentiment** — Bullish / Bearish / Neutral / Mixed — with a brief confidence note based on coverage volume and quality, and an explicit acknowledgement that no retail or social data was available.
2. **Source-by-source breakdown** — what the company coverage and the Indian market press each tell you, with specific evidence (cite headlines and dates), noting where a source was thin or unavailable.
3. **Divergences, alignments, and key narratives** across the two sources.
4. **Catalysts and risks** surfaced by the data.
5. **Markdown table** at the end summarizing key sentiment signals, their direction, source, and supporting evidence.

{get_language_instruction()}"""
