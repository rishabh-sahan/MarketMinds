from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from marketminds.agents.utils.core_stock_tools import (
    get_stock_data
)
from marketminds.agents.utils.technical_indicators_tools import (
    get_indicators
)
from marketminds.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from marketminds.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
    get_market_context,
)


__all__ = [
    "get_stock_data",
    "get_indicators",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_news",
    "get_insider_transactions",
    "get_global_news",
    "get_market_context",
    "get_language_instruction",
    "build_instrument_context",
    "create_msg_delete",
]


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from marketminds.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve the exchange suffix."""
    from marketminds.dataflows.india import CURRENCY_SYMBOL, split_suffix

    _, suffix = split_suffix(ticker)
    exchange = "BSE" if suffix == ".BO" else "NSE"
    index = "Sensex" if suffix == ".BO" else "Nifty 50"
    return (
        f"The instrument to analyze is `{ticker}`, listed on the {exchange} in India. "
        f"Use this exact ticker in every tool call, report, and recommendation, "
        f"preserving the exchange suffix. All prices, targets and stop-losses are in "
        f"Indian rupees ({CURRENCY_SYMBOL}); never quote them in dollars. "
        f"Judge relative performance against the {index}."
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
