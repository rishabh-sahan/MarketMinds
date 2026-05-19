"""Runs router — CRUD + background execution for analysis runs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Run
from backend.schemas import RunCreate, RunResponse, RunListResponse
from backend.services.run_service import start_run, _build_config

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunListResponse, status_code=201)
def create_run(body: RunCreate, db: Session = Depends(get_db)):
    """Create a new analysis run and start it in the background."""
    config = _build_config(body.model_dump())

    run = Run(
        ticker=body.ticker.upper(),
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


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    """Get full run detail with events."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
