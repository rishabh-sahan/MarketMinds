"""Run service — spawns TradingAgentsGraph in a background thread and streams events."""

from __future__ import annotations

import asyncio
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Run, RunEvent
from backend.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_ws_loop: Optional[asyncio.AbstractEventLoop] = None


def set_ws_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the main event loop for cross-thread WS emits."""
    global _ws_loop
    _ws_loop = loop


def _get_ws_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop for ws_manager emissions."""
    if _ws_loop and _ws_loop.is_running():
        return _ws_loop
    raise RuntimeError("WebSocket event loop is not initialized")


def _build_config(run_create_data: dict) -> dict:
    """Build a TradingAgents config dict from the run creation request."""
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = run_create_data.get("llm_provider", config["llm_provider"])
    config["deep_think_llm"] = run_create_data.get("deep_think_llm", config["deep_think_llm"])
    config["quick_think_llm"] = run_create_data.get("quick_think_llm", config["quick_think_llm"])
    config["max_debate_rounds"] = run_create_data.get("max_debate_rounds", config["max_debate_rounds"])
    config["max_risk_discuss_rounds"] = run_create_data.get("max_risk_discuss_rounds", config["max_risk_discuss_rounds"])
    config["output_language"] = run_create_data.get("output_language", config["output_language"])
    return config


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


def _run_analysis(run_id: str, ticker: str, trade_date: str, config: dict, selected_analysts: list, loop: asyncio.AbstractEventLoop):
    """Execute the TradingAgents pipeline (runs in a background thread)."""
    db = SessionLocal()
    try:
        # Mark as running
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        # Emit start event
        asyncio.run_coroutine_threadsafe(
            ws_manager.emit_log(run_id, f"Starting analysis for {ticker} on {trade_date}"),
            loop,
        )

        # Import here to avoid circular imports and keep startup fast
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        asyncio.run_coroutine_threadsafe(
            ws_manager.emit_log(run_id, "Initializing TradingAgentsGraph..."),
            loop,
        )

        ta = TradingAgentsGraph(
            selected_analysts=selected_analysts,
            debug=True,
            config=config,
        )

        # Run the pipeline — this streams internally via debug mode
        asyncio.run_coroutine_threadsafe(
            ws_manager.emit_log(run_id, "Running agent pipeline — this may take several minutes..."),
            loop,
        )

        final_state, decision = ta.propagate(ticker, trade_date)

        # Extract reports from final state
        result_data = {
            "market_report": final_state.get("market_report", ""),
            "sentiment_report": final_state.get("sentiment_report", ""),
            "news_report": final_state.get("news_report", ""),
            "fundamentals_report": final_state.get("fundamentals_report", ""),
            "investment_plan": final_state.get("investment_plan", ""),
            "trader_investment_plan": final_state.get("trader_investment_plan", ""),
            "final_trade_decision": final_state.get("final_trade_decision", ""),
        }

        # Add debate states if available
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

        # Update DB
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.final_decision = str(decision)
        run.result_json = result_data
        db.commit()

        _store_event(db, run_id, "system", "run_complete", {"decision": str(decision)})

        asyncio.run_coroutine_threadsafe(
            ws_manager.emit_run_complete(run_id, str(decision)),
            loop,
        )

    except Exception as e:
        logger.exception("Run %s failed", run_id)
        error_msg = f"{type(e).__name__}: {e}"
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = error_msg
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
            _store_event(db, run_id, "system", "error", {"error": error_msg, "traceback": traceback.format_exc()})
        except Exception:
            pass

        asyncio.run_coroutine_threadsafe(
            ws_manager.emit_run_error(run_id, error_msg),
            loop,
        )

    finally:
        db.close()


def start_run(run_id: str, ticker: str, trade_date: str, config: dict, selected_analysts: list):
    """Launch a background thread for the analysis run."""
    loop = _get_ws_loop()
    t = threading.Thread(
        target=_run_analysis,
        args=(run_id, ticker, trade_date, config, selected_analysts, loop),
        daemon=True,
        name=f"run-{run_id[:8]}",
    )
    t.start()
