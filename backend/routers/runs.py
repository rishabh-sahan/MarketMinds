"""Runs router — CRUD + background execution for analysis runs."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.auth import AuthUser, auth_enabled, optional_user, require_user
from backend.database import get_db
from backend.models import Run
from backend.schemas import RunCreate, RunResponse, RunListResponse, RunStatsResponse
from backend.services.run_service import start_run, request_cancel, _build_config


def _scope_to_viewer(query, user: Optional[AuthUser]):
    """Restrict a runs query to what this caller may see.

    A run belongs to whoever started it. Signed out, only runs explicitly
    marked public are visible — that is the read-only demo on the landing
    dashboard, not somebody's history.

    An instance with no Supabase configured has no notion of a user at all, so
    it stays open and unfiltered. That is the local-development case; it means
    the check below is the *only* thing separating users, so it is applied in
    every read path rather than left to the caller to remember.
    """
    if not auth_enabled():
        return query
    if user is None:
        return query.filter(Run.is_public == 1)
    return query.filter(Run.user_id == user.id)


def _demo_selection(db: Session, seed: Optional[str], limit: int = 6) -> list[Run]:
    """Pick the showcase runs a signed-out visitor sees, varied per visitor.

    Drawn only from runs whose owner published them (``is_public``), never
    from the table at large. That distinction is the whole safeguard: a
    "random run from the database" would hand a stranger somebody's private
    research the moment a second person signs up. Publishing stays an opt-in
    act by the run's owner.

    The order is a deterministic shuffle keyed by the visitor's own seed, so
    two people see different runs while each sees a stable set across reloads
    — a selection that reshuffled on every request would make the dashboard
    flicker and the numbers below it disagree with the list.

    Shuffled in Python rather than by SQL: ``ORDER BY random()`` cannot be
    seeded per caller, and ``md5()`` is unavailable on SQLite, which the local
    checkout still uses. The published pool is small by nature, so sorting it
    in memory costs nothing.
    """
    runs = db.query(Run).filter(Run.is_public == 1).all()
    if not runs:
        return []
    # A missing seed still needs an order; fall back to a fixed one so the
    # page renders the same for a client that sends nothing.
    shuffled = sorted(runs, key=lambda r: hashlib.sha256(
        f"{seed or 'default'}:{r.id}".encode()
    ).hexdigest())
    return shuffled[:limit]


def _get_visible_run(db: Session, run_id: str, user: Optional[AuthUser]) -> Run:
    """Fetch a run the caller is allowed to see, or 404.

    Deliberately 404 and not 403 for someone else's run: a 403 would confirm
    that a given run id exists, which is more than a stranger should learn.
    """
    run = _scope_to_viewer(db.query(Run).filter(Run.id == run_id), user).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _get_owned_run(db: Session, run_id: str, user: Optional[AuthUser]) -> Run:
    """Fetch a run the caller may modify — cancel or delete.

    Stricter than :func:`_get_visible_run`: a public demo run is readable by
    everyone but must remain modifiable only by its owner.
    """
    query = db.query(Run).filter(Run.id == run_id)
    if auth_enabled():
        if user is None:
            # Would otherwise match the legacy rows whose user_id is NULL.
            raise HTTPException(status_code=404, detail="Run not found")
        query = query.filter(Run.user_id == user.id)
    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Statuses that mean the run is over; anything else may still be executing.
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


@router.post("", response_model=RunListResponse, status_code=201)
def create_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Create a new analysis run and start it in the background.

    The one place sign-in is required. Everything else on the site can be
    browsed signed out; starting a run spends real time and quota, so it is
    attributed to someone.
    """
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

    # `api_key` is declared exclude=True so it never appears in responses,
    # logs or a model_dump() that might be persisted — which also means
    # model_dump() drops it here. Re-attach it deliberately: this is the one
    # place it is meant to travel.
    payload = body.model_dump()
    payload["api_key"] = body.api_key
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
        result = check_model(
            config["llm_provider"], model, config.get("backend_url"), config.get("api_key")
        )
        if not result.ok:
            raise HTTPException(status_code=422, detail=f"{label}: {result.reason}")

    run = Run(
        user_id=user.id if user else None,
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
    seed: Optional[str] = Query(None, max_length=64),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(optional_user),
):
    """List the caller's runs, or the published showcase when signed out.

    ``seed`` is the visitor's own random string, so the showcase differs
    between people. It is ignored for a signed-in caller, whose own history is
    not something to shuffle.
    """
    if auth_enabled() and user is None:
        return _demo_selection(db, seed)

    q = _scope_to_viewer(db.query(Run), user).order_by(Run.created_at.desc())
    if ticker:
        q = q.filter(Run.ticker == ticker.upper())
    if status:
        q = q.filter(Run.status == status)
    return q.offset(offset).limit(limit).all()


@router.get("/stats", response_model=RunStatsResponse)
def run_stats(
    seed: Optional[str] = Query(None, max_length=64),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(optional_user),
):
    """Aggregate counters over the caller's runs, for the dashboard.

    Computed server-side so the dashboard reflects the whole history rather
    than only the page of runs the client happens to have fetched.

    Signed out, the counters describe the same showcase selection the list
    returns — computed over the whole published pool they would contradict
    the handful of runs actually on screen.
    """
    if auth_enabled() and user is None:
        runs = _demo_selection(db, seed)
    else:
        runs = _scope_to_viewer(db.query(Run), user).all()

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
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(optional_user),
):
    """Get full run detail with events."""
    return _get_visible_run(db, run_id, user)


@router.post("/{run_id}/cancel", response_model=RunListResponse)
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Ask an in-flight run to stop at the next agent boundary.

    Cancellation is cooperative — the flag is checked between graph nodes, so
    the agent currently talking to its provider finishes that call first.
    """
    run = _get_owned_run(db, run_id, user)
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
def delete_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Delete a run and its events. In-flight runs must be cancelled first."""
    run = _get_owned_run(db, run_id, user)
    if run.status not in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Cancel the run before deleting it",
        )
    db.delete(run)
    db.commit()


# Report sections in the order they appear in an exported document, paired
# with the path into `result_json`. Debate histories are nested, so each entry
# carries the group it lives under.
_EXPORT_SECTIONS = (
    ("Market Analyst", ("market_report",)),
    ("Sentiment Analyst", ("sentiment_report",)),
    ("News Analyst", ("news_report",)),
    ("Fundamentals Analyst", ("fundamentals_report",)),
    ("Bull Researcher", ("investment_debate", "bull_history")),
    ("Bear Researcher", ("investment_debate", "bear_history")),
    ("Research Manager — Investment Plan", ("investment_plan",)),
    ("Trader — Transaction Proposal", ("trader_investment_plan",)),
    ("Aggressive Analyst", ("risk_debate", "aggressive_history")),
    ("Conservative Analyst", ("risk_debate", "conservative_history")),
    ("Neutral Analyst", ("risk_debate", "neutral_history")),
    ("Portfolio Manager — Final Decision", ("final_trade_decision",)),
)


def _read_section(result: dict, path: tuple) -> str:
    node = result
    for step in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(step)
    return node if isinstance(node, str) else ""


@router.get("/{run_id}/export")
def export_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(optional_user),
):
    """Download a completed run as a PDF."""
    from marketminds.reporting import build_run_pdf, run_pdf_filename

    run = _get_visible_run(db, run_id, user)
    if not run.result_json:
        raise HTTPException(status_code=409, detail="Run has no results to export")

    result = run.result_json
    cfg = run.config_snapshot or {}

    sections = [
        (heading, _read_section(result, path)) for heading, path in _EXPORT_SECTIONS
    ]

    usage = None
    if run.llm_calls or run.tokens_in:
        usage = (
            f"{run.llm_calls} LLM calls · {run.tool_calls} tool calls · "
            f"{run.tokens_in:,} input tokens · {run.tokens_out:,} output tokens"
        )

    analysts = cfg.get("selected_analysts") or []
    generated = (run.completed_at or run.created_at)

    pdf = build_run_pdf(
        ticker=run.ticker,
        trade_date=run.trade_date,
        rating=run.final_decision,
        sections=sections,
        meta={
            "exchange": cfg.get("exchange"),
            "benchmark": cfg.get("benchmark"),
            "provider": cfg.get("llm_provider"),
            "deep_model": cfg.get("deep_think_llm"),
            "quick_model": cfg.get("quick_think_llm"),
            "analysts": ", ".join(analysts) if analysts else None,
            "rounds": (
                f"{cfg.get('max_debate_rounds', '?')} bull/bear · "
                f"{cfg.get('max_risk_discuss_rounds', '?')} risk"
            ),
            "generated": generated.strftime("%d %b %Y, %H:%M") if generated else None,
            "usage": usage,
        },
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{run_pdf_filename(run.ticker, run.trade_date)}"'
        },
    )
