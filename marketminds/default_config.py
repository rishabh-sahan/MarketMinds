import os

_MARKETMINDS_HOME = os.path.join(os.path.expanduser("~"), ".marketminds")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "MARKETMINDS_LLM_PROVIDER":         "llm_provider",
    "MARKETMINDS_DEEP_THINK_LLM":       "deep_think_llm",
    "MARKETMINDS_QUICK_THINK_LLM":      "quick_think_llm",
    "MARKETMINDS_LLM_BACKEND_URL":      "backend_url",
    "MARKETMINDS_OUTPUT_LANGUAGE":      "output_language",
    "MARKETMINDS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "MARKETMINDS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "MARKETMINDS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "MARKETMINDS_BENCHMARK_TICKER":     "benchmark_ticker",
    "MARKETMINDS_REQUIRE_TRADING_DAY":  "require_trading_day",
}


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply MARKETMINDS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("MARKETMINDS_RESULTS_DIR", os.path.join(_MARKETMINDS_HOME, "logs")),
    "data_cache_dir": os.getenv("MARKETMINDS_CACHE_DIR", os.path.join(_MARKETMINDS_HOME, "cache")),
    "memory_log_path": os.getenv("MARKETMINDS_MEMORY_LOG_PATH", os.path.join(_MARKETMINDS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Macro themes fetched by get_global_news. These drive Indian equities
    # specifically; the full topic set lives in
    # marketminds/dataflows/india_news.MACRO_TOPICS and this list selects
    # which of those to run. Empty means "all topics".
    "macro_news_topics": [],
    # Sector coverage pulled alongside the macro block. Empty means "all
    # sectors" (see india_news.SECTOR_TOPICS).
    "sector_news_topics": [],
    # Include the live index / currency / commodity snapshot in the news brief.
    "include_market_context": True,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer. MarketMinds
    # covers Indian listings only: NSE names are measured against the Nifty 50
    # and BSE names against the Sensex. Set ``benchmark_ticker`` to force one
    # benchmark for every run (e.g. "^NSEBANK" for a bank-only portfolio);
    # leave it None to pick from the exchange suffix.
    "benchmark_ticker": None,
    "benchmark_map": {
        ".NS": "^NSEI",    # NSE India (Nifty 50)
        ".BO": "^BSESN",   # BSE India (Sensex)
        "":    "^NSEI",    # bare names resolve to NSE, so Nifty 50
    },
    # Analysis dates are interpreted in IST — the market's own day — rather
    # than the host timezone, and validated against the NSE trading calendar.
    "market_timezone": "Asia/Kolkata",
    "currency": "INR",
    # Reject an analysis date on which the exchange was closed. Turn off to
    # allow backtesting against a non-trading date.
    "require_trading_day": True,
})
