"""Run service — spawns MarketMindsGraph in a background thread and streams events."""

from __future__ import annotations

import asyncio
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Run, RunEvent
from backend.services.run_tracker import RunTracker
from backend.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_ws_loop: Optional[asyncio.AbstractEventLoop] = None

# Cancellation flags for in-flight runs, keyed by run id. The analysis runs in
# a plain thread with no safe way to interrupt it mid-LLM-call, so cancellation
# is cooperative: the flag is checked between graph nodes.
_cancel_flags: Dict[str, threading.Event] = {}
_cancel_lock = threading.Lock()


class RunCancelled(Exception):
    """Raised inside the graph stream to unwind a cancelled run."""


def set_ws_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the main event loop for cross-thread WS emits."""
    global _ws_loop
    _ws_loop = loop


def _get_ws_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop for ws_manager emissions."""
    if _ws_loop and _ws_loop.is_running():
        return _ws_loop
    raise RuntimeError("WebSocket event loop is not initialized")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def request_cancel(run_id: str) -> bool:
    """Signal an in-flight run to stop. Returns False if it isn't running."""
    with _cancel_lock:
        flag = _cancel_flags.get(run_id)
    if flag is None:
        return False
    flag.set()
    return True


def is_active(run_id: str) -> bool:
    """Whether a run is currently executing in this process."""
    with _cancel_lock:
        return run_id in _cancel_flags


def _register(run_id: str) -> threading.Event:
    flag = threading.Event()
    with _cancel_lock:
        _cancel_flags[run_id] = flag
    return flag


def _unregister(run_id: str) -> None:
    with _cancel_lock:
        _cancel_flags.pop(run_id, None)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Each provider exposes its thinking budget under a different config key; the
# API takes one `reasoning_effort` field and routes it to the right one.
_EFFORT_KEY_BY_PROVIDER = {
    "openai": "openai_reasoning_effort",
    "google": "google_thinking_level",
    "anthropic": "anthropic_effort",
}


def _build_config(run_create_data: dict) -> dict:
    """Build a MarketMinds config dict from the run creation request."""
    from marketminds.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()

    for key in (
        "llm_provider",
        "deep_think_llm",
        "quick_think_llm",
        "max_debate_rounds",
        "max_risk_discuss_rounds",
        "output_language",
    ):
        value = run_create_data.get(key)
        if value is not None:
            config[key] = value

    # Advanced, all optional — absent means "keep the global default".
    if run_create_data.get("backend_url"):
        config["backend_url"] = run_create_data["backend_url"]
    if run_create_data.get("checkpoint_enabled") is not None:
        config["checkpoint_enabled"] = bool(run_create_data["checkpoint_enabled"])
    if run_create_data.get("data_vendors"):
        config["data_vendors"] = {**config.get("data_vendors", {}), **run_create_data["data_vendors"]}
    for key in ("news_article_limit", "global_news_article_limit", "global_news_lookback_days"):
        if run_create_data.get(key) is not None:
            config[key] = run_create_data[key]

    # Transient credential, kept out of every persisted structure. The graph
    # reads it when constructing its clients and nothing else touches it.
    api_key = run_create_data.get("api_key")
    if api_key:
        config["api_key"] = api_key

    effort = run_create_data.get("reasoning_effort")
    if effort:
        effort_key = _EFFORT_KEY_BY_PROVIDER.get(str(config.get("llm_provider", "")).lower())
        if effort_key:
            config[effort_key] = effort

    return config


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _store_event(db: Session, run_id: str, agent_name: str, event_type: str, payload: dict = None):
    """Write a RunEvent row."""
    ev = RunEvent(
        run_id=run_id,
        agent_name=agent_name,
        event_type=event_type,
        payload=payload,
    )
    db.add(ev)
    db.commit()


def _extract_results(final_state: dict) -> dict:
    """Pull the report sections out of the final graph state."""
    result_data = {
        "market_report": final_state.get("market_report", ""),
        "sentiment_report": final_state.get("sentiment_report", ""),
        "news_report": final_state.get("news_report", ""),
        "fundamentals_report": final_state.get("fundamentals_report", ""),
        "investment_plan": final_state.get("investment_plan", ""),
        "trader_investment_plan": final_state.get("trader_investment_plan", ""),
        "final_trade_decision": final_state.get("final_trade_decision", ""),
    }

    if "investment_debate_state" in final_state:
        ids = final_state["investment_debate_state"]
        result_data["investment_debate"] = {
            "bull_history": ids.get("bull_history", ""),
            "bear_history": ids.get("bear_history", ""),
            "judge_decision": ids.get("judge_decision", ""),
        }

    if "risk_debate_state" in final_state:
        rds = final_state["risk_debate_state"]
        result_data["risk_debate"] = {
            "aggressive_history": rds.get("aggressive_history", ""),
            "conservative_history": rds.get("conservative_history", ""),
            "neutral_history": rds.get("neutral_history", ""),
            "judge_decision": rds.get("judge_decision", ""),
        }

    return result_data


def _run_analysis(
    run_id: str,
    ticker: str,
    trade_date: str,
    config: dict,
    selected_analysts: list,
    loop: asyncio.AbstractEventLoop,
    cancel_flag: threading.Event,
):
    """Execute the MarketMinds pipeline (runs in a background thread)."""
    db = SessionLocal()
    tracker = RunTracker(selected_analysts)

    def emit(coro):
        """Schedule a ws_manager coroutine on the server's event loop."""
        asyncio.run_coroutine_threadsafe(coro, loop)

    def log(message: str, level: str = "info"):
        emit(ws_manager.emit_log(run_id, message, level))

    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.agent_status = tracker.snapshot()
        db.commit()

        emit(ws_manager.emit_status(run_id, "running"))
        emit(ws_manager.emit_agent_snapshot(run_id, tracker.snapshot()))
        log(f"Starting analysis for {ticker} on {trade_date}")

        # Imported here to avoid circular imports and keep server startup fast.
        from backend.services.db_memory import DatabaseMemoryLog
        from cli.stats_handler import StatsCallbackHandler
        from marketminds.graph.trading_graph import MarketMindsGraph

        # The web app keeps its decision log in the database, not in a file:
        # a deployed container's disk does not survive a restart, and this log
        # is the state whose loss makes later analyses worse. Written against
        # the run's owner so the Memory page can show a user only their own,
        # while every run still learns from the whole pool.
        #
        # Passed to the graph directly, never through `config`: the config dict
        # is deep-copied by `set_config`, and this object holds a session
        # factory that cannot be copied.
        memory_log = DatabaseMemoryLog(
            SessionLocal,
            user_id=run.user_id,
            max_entries=config.get("memory_log_max_entries"),
        )

        # State logs stay off — `runs.result_json` already holds the same
        # state, so the file copy is pure duplication. A plain bool, so it is
        # safe in config.
        config = {**config, "save_state_logs": False}

        stats_handler = StatsCallbackHandler()

        def on_chunk(chunk: Dict[str, Any]) -> None:
            """Fold each streamed graph state into events for the UI."""
            if cancel_flag.is_set():
                raise RunCancelled()

            for event in tracker.ingest(chunk):
                kind = event["type"]
                if kind == "agent_start":
                    emit(ws_manager.emit_agent_start(run_id, event["agent"]))
                    _store_event(db, run_id, event["agent"], "agent_start")
                elif kind == "agent_complete":
                    emit(ws_manager.emit_agent_complete(run_id, event["agent"]))
                    _store_event(db, run_id, event["agent"], "agent_complete")
                elif kind == "tool_call":
                    emit(ws_manager.emit_tool_call(run_id, event["agent"], event["tool"], event["args"]))
                    _store_event(
                        db, run_id, event["agent"], "tool_call",
                        {"tool": event["tool"], "args": event["args"]},
                    )
                elif kind == "report_update":
                    emit(ws_manager.emit_report_update(
                        run_id, event["agent"], event["report_key"], event["report_content"],
                    ))
                    _store_event(
                        db, run_id, event["agent"], "report_update",
                        {"report_key": event["report_key"], "report_content": event["report_content"]},
                    )

            # Persist the pipeline snapshot so a reconnect restores the view,
            # and push live usage counters alongside it.
            snapshot = tracker.snapshot()
            stats = stats_handler.get_stats()
            run.agent_status = snapshot
            run.llm_calls = stats["llm_calls"]
            run.tool_calls = stats["tool_calls"]
            run.tokens_in = stats["tokens_in"]
            run.tokens_out = stats["tokens_out"]
            db.commit()

            emit(ws_manager.emit_agent_snapshot(run_id, snapshot))
            emit(ws_manager.emit_stats(run_id, stats))

        log("Initializing agent graph...")

        ta = MarketMindsGraph(
            selected_analysts=selected_analysts,
            debug=False,
            config=config,
            callbacks=[stats_handler],
            on_chunk=on_chunk,
            memory_log=memory_log,
        )

        log("Running agent pipeline — this may take several minutes...")

        final_state, decision = ta.propagate(ticker, trade_date)

        result_data = _extract_results(final_state)
        stats = stats_handler.get_stats()

        for event in tracker.finish_all():
            if event["type"] == "agent_complete":
                emit(ws_manager.emit_agent_complete(run_id, event["agent"]))

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.final_decision = str(decision)
        run.result_json = result_data
        run.agent_status = tracker.snapshot()
        run.llm_calls = stats["llm_calls"]
        run.tool_calls = stats["tool_calls"]
        run.tokens_in = stats["tokens_in"]
        run.tokens_out = stats["tokens_out"]
        db.commit()

        _store_event(db, run_id, "system", "run_complete", {"decision": str(decision)})

        emit(ws_manager.emit_agent_snapshot(run_id, tracker.snapshot()))
        emit(ws_manager.emit_stats(run_id, stats))
        emit(ws_manager.emit_run_complete(run_id, str(decision)))

    except RunCancelled:
        logger.info("Run %s cancelled by user", run_id)
        try:
            db.rollback()
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "cancelled"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = "Cancelled by user"
                db.commit()
            _store_event(db, run_id, "system", "run_cancelled", None)
        except Exception:
            logger.exception("Failed to record cancellation for run %s", run_id)

        emit(ws_manager.emit_run_cancelled(run_id))

    except Exception as e:
        logger.exception("Run %s failed", run_id)
        error_msg = f"{type(e).__name__}: {e}"
        try:
            db.rollback()
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = error_msg
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
            _store_event(db, run_id, "system", "error", {"error": error_msg, "traceback": traceback.format_exc()})
        except Exception:
            logger.exception("Failed to record failure for run %s", run_id)

        emit(ws_manager.emit_run_error(run_id, error_msg))

    finally:
        _unregister(run_id)
        db.close()


def start_run(run_id: str, ticker: str, trade_date: str, config: dict, selected_analysts: list):
    """Launch a background thread for the analysis run."""
    loop = _get_ws_loop()
    cancel_flag = _register(run_id)
    t = threading.Thread(
        target=_run_analysis,
        args=(run_id, ticker, trade_date, config, selected_analysts, loop, cancel_flag),
        daemon=True,
        name=f"run-{run_id[:8]}",
    )
    t.start()
