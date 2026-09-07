# MarketMinds/graph/trading_graph.py

import logging
import os
from pathlib import Path
import json
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Tuple, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

from langgraph.prebuilt import ToolNode

from marketminds.llm_clients import create_llm_client

from marketminds.default_config import DEFAULT_CONFIG
from marketminds.agents.utils.memory import TradingMemoryLog
from marketminds.dataflows.utils import safe_ticker_component
from marketminds.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from marketminds.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news,
    get_market_context,
)

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class IncompleteAnalysisError(RuntimeError):
    """Raised when the pipeline finishes without producing its decision.

    Distinct from a provider error: every call succeeded, but the agents
    returned nothing usable, so there is no rating to report.
    """


class MarketMindsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
        on_chunk: Optional[Callable[[Dict[str, Any]], None]] = None,
        memory_log=None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            memory_log: Decision-log store. Defaults to the markdown log built
                from ``config``; the web backend passes a database-backed one.
                A parameter rather than a config key on purpose — ``config`` is
                deep-copied by ``set_config``, and a live object with a database
                session in it cannot be copied.
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
            on_chunk: Optional callable invoked with each per-node state delta as
                the graph streams. Lets an embedding application (the web backend)
                observe progress live without reimplementing propagate()'s
                memory-log and reflection semantics. Raising from inside the
                callback aborts the run, which is how cancellation is signalled.
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        self.on_chunk = on_chunk

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        # A caller-supplied credential overrides the environment, so a hosted
        # instance can run on the visitor's own key. It lives only in this
        # config dict for the duration of the run.
        if self.config.get("api_key"):
            llm_kwargs["api_key"] = self.config["api_key"]

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
        
        # The decision log is injectable so a deployed instance can keep it in
        # the database instead of a file — same interface, different store.
        # The CLI and local runs get the markdown log by default.
        self.memory_log = memory_log or TradingMemoryLog(self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
        )

        self.propagator = Propagator(
            max_recur_limit=self.config.get("max_recur_limit", 100),
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph: keep the workflow for recompilation with a checkpointer.
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                    # Index, sector, currency and commodity backdrop, so a
                    # single stock's move is read against its own market.
                    get_market_context,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # Company news, Indian macro/policy/sector brief, and
                    # insider activity plus exchange filings
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                    get_market_context,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def _resolve_benchmark(self, ticker: str) -> str:
        """Pick the alpha benchmark for ``ticker``.

        ``config["benchmark_ticker"]`` overrides everything when set — useful
        for measuring a bank against the Nifty Bank rather than the Nifty 50.
        Otherwise the exchange suffix decides: NSE listings are measured
        against the Nifty 50 and BSE listings against the Sensex. Bare names
        resolve to NSE, so they take the Nifty 50 too.
        """
        explicit = self.config.get("benchmark_ticker")
        if explicit:
            return explicit

        from marketminds.dataflows.india import DEFAULT_BENCHMARK, split_suffix

        _, suffix = split_suffix(ticker)
        benchmark_map = self.config.get("benchmark_map", {})
        if suffix and suffix in benchmark_map:
            return benchmark_map[suffix]
        return benchmark_map.get("", DEFAULT_BENCHMARK)

    def _fetch_returns(
        self, ticker: str, trade_date: str, holding_days: int = 5,
        benchmark: str = "^NSEI",
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        """Fetch raw and alpha return for ticker over holding_days from trade_date.

        ``benchmark`` is the index used as the alpha baseline (resolved by the
        caller via ``_resolve_benchmark``). Returns ``(raw_return, alpha_return,
        actual_holding_days)`` or ``(None, None, None)`` if price data is
        unavailable (too recent, delisted, or network error).
        """
        try:
            start = datetime.strptime(trade_date, "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)  # buffer for weekends/holidays
            end_str = end.strftime("%Y-%m-%d")

            stock = yf.Ticker(ticker).history(start=trade_date, end=end_str)
            bench = yf.Ticker(benchmark).history(start=trade_date, end=end_str)

            if len(stock) < 2 or len(bench) < 2:
                return None, None, None

            actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                / stock["Close"].iloc[0]
            )
            bench_ret = float(
                (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
                / bench["Close"].iloc[0]
            )
            alpha = raw - bench_ret
            return raw, alpha, actual_days
        except Exception as e:
            logger.warning(
                "Could not resolve outcome for %s on %s vs %s (will retry next run): %s",
                ticker, trade_date, benchmark, e,
            )
            return None, None, None

    def _resolve_pending_entries(self, ticker: str) -> None:
        """Resolve pending log entries for ticker at the start of a new run.

        Fetches returns for each same-ticker pending entry, generates reflections,
        then writes all updates in a single atomic batch write to avoid redundant I/O.
        Skips entries whose price data is not yet available (too recent or delisted).

        Trade-off: only same-ticker entries are resolved per run.  Entries for
        other tickers accumulate until that ticker is run again.
        """
        pending = [e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker]
        if not pending:
            return

        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker, entry["date"], benchmark=benchmark,
            )
            if raw is None:
                continue  # price not available yet — try again next run
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
                benchmark_name=benchmark,
            )
            updates.append({
                "ticker": ticker,
                "trade_date": entry["date"],
                "raw_return": raw,
                "alpha_return": alpha,
                "holding_days": days,
                "reflection": reflection,
            })

        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def propagate(self, company_name, trade_date):
        """Run the trading agents graph for a company on a specific date.

        ``company_name`` is resolved to an exchange-qualified Indian symbol
        first: the price source returns nothing for a bare NSE name, and the
        indicator path degrades to blank values rather than an error, so an
        unresolved ticker would yield a confident report built on no data.

        When ``checkpoint_enabled`` is set in config, the graph is recompiled
        with a per-ticker SqliteSaver so a crashed run can resume from the last
        successful node on a subsequent invocation with the same ticker+date.
        """
        from marketminds.dataflows.india import describe_session, is_trading_day, resolve_ticker

        resolved = resolve_ticker(company_name)
        if resolved.symbol != company_name:
            logger.info("Resolved ticker %s -> %s", company_name, resolved.symbol)
        company_name = resolved.symbol

        if self.config.get("require_trading_day", True) and not is_trading_day(trade_date):
            raise ValueError(describe_session(trade_date))

        self.ticker = company_name

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
            if step is not None:
                logger.info(
                    "Resuming from step %d for %s on %s", step, company_name, trade_date
                )
            else:
                logger.info("Starting fresh for %s on %s", company_name, trade_date)

        try:
            return self._run_graph(company_name, trade_date)
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

    def _run_graph(self, company_name, trade_date):
        """Execute the graph and write the resulting state to disk and memory log."""
        # Initialize state — inject memory log context for PM.
        past_context = self.memory_log.get_past_context(company_name)
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, past_context=past_context
        )
        args = self.propagator.get_graph_args(callbacks=self.callbacks or None)

        # Inject thread_id so same ticker+date resumes, different date starts fresh.
        if self.config.get("checkpoint_enabled"):
            tid = thread_id(company_name, str(trade_date))
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = tid

        if self.debug or self.on_chunk:
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if self.on_chunk:
                    self.on_chunk(chunk)
                if not chunk.get("messages"):
                    if self.on_chunk:
                        trace.append(chunk)
                    continue
                if self.debug:
                    chunk["messages"][-1].pretty_print()
                trace.append(chunk)
            # Streamed chunks are per-node deltas. Merge them so the returned
            # state matches what graph.invoke() yields in the non-debug path.
            final_state = {}
            for chunk in trace:
                final_state.update(chunk)
        else:
            final_state = self.graph.invoke(init_agent_state, **args)

        # Refuse to present an incomplete run as a finished one. An agent that
        # returns empty text still advances the graph, so without this check a
        # run where most agents produced nothing is recorded as "completed" —
        # and an empty Portfolio Manager decision parses to the default "Hold",
        # presenting a rating that nothing actually decided.
        self._assert_analysis_complete(final_state)

        # Store current state for reflection.
        self.curr_state = final_state

        # Log state to disk.
        self._log_state(trade_date, final_state)

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear checkpoint on successful completion to avoid stale state.
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )

        return final_state, self.process_signal(final_state["final_trade_decision"])

    # Sections the pipeline must produce for a run to mean anything, mapped to
    # the agent responsible. Analyst reports are checked separately, since
    # which ones are expected depends on the team selected for the run.
    _REQUIRED_SECTIONS = {
        "investment_plan": "Research Manager",
        "trader_investment_plan": "Trader",
        "final_trade_decision": "Portfolio Manager",
    }

    _ANALYST_SECTIONS = {
        "market": ("market_report", "Market Analyst"),
        "social": ("sentiment_report", "Sentiment Analyst"),
        "news": ("news_report", "News Analyst"),
        "fundamentals": ("fundamentals_report", "Fundamentals Analyst"),
    }

    def _assert_analysis_complete(self, final_state: Dict[str, Any]) -> None:
        """Raise when agents finished without producing their output.

        Some models — particularly ones that handle bound tools poorly — keep
        requesting tools and never write their report, or return an empty
        completion. The graph advances regardless, because an empty string is
        a valid state value. The result is a run that looks successful while
        being mostly blank, topped by a "Hold" that came from the rating
        parser's default rather than from any analysis.
        """
        def blank(key: str) -> bool:
            return not str(final_state.get(key) or "").strip()

        empty = [
            f"{agent} ({key})"
            for key, agent in self._REQUIRED_SECTIONS.items()
            if blank(key)
        ]

        for key, agent in self._ANALYST_SECTIONS.values():
            if key in final_state and blank(key):
                empty.append(f"{agent} ({key})")

        # The debate histories carry the researchers' and risk committee's
        # arguments; a name label with nothing after it is effectively empty.
        for state_key, fields in (
            ("investment_debate_state", ("bull_history", "bear_history")),
            (
                "risk_debate_state",
                ("aggressive_history", "conservative_history", "neutral_history"),
            ),
        ):
            debate = final_state.get(state_key) or {}
            for field in fields:
                text = str(debate.get(field) or "")
                # Strip the "Aggressive Analyst: " style prefix before judging.
                body = text.split(":", 1)[-1] if ":" in text else text
                if not body.strip():
                    empty.append(f"{field}")

        if not empty:
            return

        decision_missing = blank("final_trade_decision")
        detail = ", ".join(empty)

        if decision_missing:
            raise IncompleteAnalysisError(
                "The analysis did not complete: the Portfolio Manager produced no "
                "decision, so there is no rating. Empty sections: "
                f"{detail}. This usually means the model returned empty responses "
                "or kept calling tools without writing its report — try a model "
                "that handles tool loops reliably, or reduce the prompt size."
            )

        logger.warning(
            "Run finished with empty sections (rating still produced): %s", detail
        )

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file. The web app turns this off: it already persists the
        # same state as `runs.result_json`, so writing it again would only
        # scatter copies across a disk that does not survive a restart.
        if not self.config.get("save_state_logs", True):
            return

        # Reject ticker values that would escape the results directory when
        # joined as a path component.
        safe_ticker = safe_ticker_component(self.ticker)
        directory = Path(self.config["results_dir"]) / safe_ticker / "MarketMindsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict[str(trade_date)], f, indent=4)

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
