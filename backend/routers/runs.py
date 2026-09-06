"""Runs router — CRUD + background execution for analysis runs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Run
from backend.schemas import RunCreate, RunResponse, RunListResponse, RunStatsResponse
from backend.services.run_service import start_run, request_cancel, _build_config

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Statuses that mean the run is over; anything else may still be executing.
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


@router.post("", response_model=RunListResponse, status_code=201)
def create_run(body: RunCreate, db: Session = Depends(get_db)):
    """Create a new analysis run and start it in the background."""
    if not body.selected_analysts:
        raise HTTPException(status_code=422, detail="Select at least one analyst")

    # Resolve and validate before anything is stored. The price source returns
    # nothing for a bare NSE name and the indicator path degrades to blank
    # values rather than erroring, so an unresolved ticker would otherwise
    # surface minutes later as a confident report built on no data.
    from marketminds.dataflows.india import (
        NotAnIndianTickerError,
        describe_session,
        is_trading_day,
        resolve_ticker,
    )

    try:
        resolved = resolve_ticker(body.ticker)
    except NotAnIndianTickerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = body.model_dump()
    config = _build_config(payload)

    if config.get("require_trading_day", True) and not is_trading_day(body.trade_date):
        raise HTTPException(status_code=422, detail=describe_session(body.trade_date))

    # Probe both models before committing. A run costs minutes and real quota,
    # and a retired or paid-tier-only model would otherwise surface as a
    # provider stack trace partway through the analyst loop.
    from marketminds.llm_clients.preflight import check_model

    for label, model in (
        ("Quick-thinking model", config["quick_think_llm"]),
        ("Deep-thinking model", config["deep_think_llm"]),
    ):
        result = check_model(config["llm_provider"], model, config.get("backend_url"))
        if not result.ok:
            raise HTTPException(status_code=422, detail=f"{label}: {result.reason}")

    run = Run(
        ticker=resolved.symbol,
        trade_date=body.trade_date,
        status="pending",
        config_snapshot={
            "llm_provider": body.llm_provider,
            "deep_think_llm": body.deep_think_llm,
            "quick_think_llm": body.quick_think_llm,
            "selected_analysts": body.selected_analysts,
            "max_debate_rounds": body.max_debate_rounds,
            "max_risk_discuss_rounds": body.max_risk_discuss_rounds,
            "output_language": body.output_language,
            "backend_url": body.backend_url,
            "reasoning_effort": body.reasoning_effort,
            "checkpoint_enabled": body.checkpoint_enabled,
            "data_vendors": body.data_vendors,
            "exchange": resolved.exchange,
            "benchmark": resolved.benchmark,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Launch background execution
    start_run(
        run_id=run.id,
        ticker=run.ticker,
        trade_date=run.trade_date,
        config=config,
        selected_analysts=body.selected_analysts,
    )

    return run


@router.get("", response_model=list[RunListResponse])
def list_runs(
    ticker: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List runs with optional filters."""
    q = db.query(Run).order_by(Run.created_at.desc())
    if ticker:
        q = q.filter(Run.ticker == ticker.upper())
    if status:
        q = q.filter(Run.status == status)
    return q.offset(offset).limit(limit).all()


@router.get("/stats", response_model=RunStatsResponse)
def run_stats(db: Session = Depends(get_db)):
    """Aggregate counters over every stored run, for the dashboard.

    Computed server-side so the dashboard reflects the whole history rather
    than only the page of runs the client happens to have fetched.
    """
    runs = db.query(Run).all()

    status_counts = Counter(r.status for r in runs)
    rating_counts = Counter(
        r.final_decision for r in runs if r.status == "completed" and r.final_decision
    )
    ticker_counts = Counter(r.ticker for r in runs)
    day_counts = Counter(
        r.created_at.date().isoformat() for r in runs if r.created_at is not None
    )

    durations = [
        (r.completed_at - r.started_at).total_seconds()
        for r in runs
        if r.status == "completed" and r.started_at and r.completed_at
    ]

    return RunStatsResponse(
        total=len(runs),
        completed=status_counts.get("completed", 0),
        running=status_counts.get("running", 0),
        failed=status_counts.get("failed", 0),
        cancelled=status_counts.get("cancelled", 0),
        pending=status_counts.get("pending", 0),
        rating_counts=dict(rating_counts),
        top_tickers=[{"ticker": t, "count": c} for t, c in ticker_counts.most_common(8)],
        runs_per_day=[{"date": d, "count": c} for d, c in sorted(day_counts.items())],
        tokens_in=sum(r.tokens_in or 0 for r in runs),
        tokens_out=sum(r.tokens_out or 0 for r in runs),
        llm_calls=sum(r.llm_calls or 0 for r in runs),
        tool_calls=sum(r.tool_calls or 0 for r in runs),
        avg_duration_seconds=(sum(durations) / len(durations)) if durations else None,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    """Get full run detail with events."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", response_model=RunListResponse)
def cancel_run(run_id: str, db: Session = Depends(get_db)):
    """Ask an in-flight run to stop at the next agent boundary.

    Cancellation is cooperative — the flag is checked between graph nodes, so
    the agent currently talking to its provider finishes that call first.
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in _TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"Run is already {run.status}")

    if not request_cancel(run_id):
        # No live thread owns this run — it was orphaned by a server restart.
        run.status = "cancelled"
        run.error_message = "Cancelled (no active worker — server likely restarted)"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return run


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(get_db)):
    """Delete a run and its events. In-flight runs must be cancelled first."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Cancel the run before deleting it",
        )
    db.delete(run)
    db.commit()


# Report sections in the order they should appear in an exported document.
_EXPORT_SECTIONS = (
    ("market_report", "Market Analyst"),
    ("sentiment_report", "Sentiment Analyst"),
    ("news_report", "News Analyst"),
    ("fundamentals_report", "Fundamentals Analyst"),
    ("investment_plan", "Research Manager — Investment Plan"),
    ("trader_investment_plan", "Trader — Transaction Proposal"),
    ("final_trade_decision", "Portfolio Manager — Final Decision"),
)


@router.get("/{run_id}/export")
def export_run(run_id: str, db: Session = Depends(get_db)):
    """Download a completed run as a single markdown document."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.result_json:
        raise HTTPException(status_code=409, detail="Run has no results to export")

    result = run.result_json
    cfg = run.config_snapshot or {}

    lines = [
        f"# {run.ticker} — MarketMinds Analysis",
        "",
        f"- **Analysis date**: {run.trade_date}",
        f"- **Final rating**: {run.final_decision or 'n/a'}",
        f"- **Provider**: {cfg.get('llm_provider', 'n/a')}",
        f"- **Deep model**: {cfg.get('deep_think_llm', 'n/a')}",
        f"- **Quick model**: {cfg.get('quick_think_llm', 'n/a')}",
        f"- **Generated**: {(run.completed_at or run.created_at).isoformat()}",
        "",
        "> Research and educational use only. Not financial advice.",
        "",
    ]

    for key, heading in _EXPORT_SECTIONS:
        content = (result.get(key) or "").strip()
        if content:
            lines.extend([f"## {heading}", "", content, ""])

    debate = result.get("investment_debate") or {}
    if any(debate.values()):
        lines.extend(["## Bull vs Bear Debate", ""])
        for key, heading in (
            ("bull_history", "Bull Researcher"),
            ("bear_history", "Bear Researcher"),
            ("judge_decision", "Research Manager Verdict"),
        ):
            content = (debate.get(key) or "").strip()
            if content:
                lines.extend([f"### {heading}", "", content, ""])

    risk = result.get("risk_debate") or {}
    if any(risk.values()):
        lines.extend(["## Risk Committee", ""])
        for key, heading in (
            ("aggressive_history", "Aggressive Analyst"),
            ("conservative_history", "Conservative Analyst"),
            ("neutral_history", "Neutral Analyst"),
            ("judge_decision", "Portfolio Manager Verdict"),
        ):
            content = (risk.get(key) or "").strip()
            if content:
                lines.extend([f"### {heading}", "", content, ""])

    filename = f"marketminds-{run.ticker}-{run.trade_date}.md"
    return Response(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
