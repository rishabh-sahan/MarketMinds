"""Timestamps crossing the API must say which timezone they are in.

Every timestamp is written with ``datetime.now(timezone.utc)``, but the ORM
columns are ``DateTime`` without ``timezone=True``, so both SQLite and
Postgres return them naive. Serialized bare — ``2026-09-07T18:21:57`` — they
are a UTC instant with nothing saying so, and JavaScript's ``new Date()``
reads a bare ISO string as *local* time.

The visible symptom was a run that had just started reporting an elapsed time
of 5h30m: exactly the IST offset. Any non-UTC viewer sees their own offset,
and viewers west of UTC would see a negative duration clamped to zero.

These tests pin the offset onto the wire format, which is the one place that
fixes every consumer at once.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.schemas import (
    RunEventResponse,
    RunListResponse,
    RunResponse,
    SavedConfigResponse,
)

NAIVE = datetime(2026, 9, 7, 18, 21, 57, 606176)


def _dump(model) -> dict:
    return json.loads(model.model_dump_json())


@pytest.mark.unit
class TestOffsetIsAlwaysPresent:
    def test_run_list_created_at_carries_utc(self):
        model = RunListResponse(
            id="x", ticker="RELIANCE.NS", trade_date="2026-09-07",
            status="running", created_at=NAIVE,
        )

        assert _dump(model)["created_at"] == "2026-09-07T18:21:57.606176+00:00"

    def test_run_detail_timestamps_all_carry_utc(self):
        model = RunResponse(
            id="x", ticker="RELIANCE.NS", trade_date="2026-09-07",
            status="completed", created_at=NAIVE, started_at=NAIVE,
            completed_at=NAIVE,
        )
        dumped = _dump(model)

        for field in ("created_at", "started_at", "completed_at"):
            assert dumped[field].endswith("+00:00"), field

    def test_event_timestamp_carries_utc(self):
        model = RunEventResponse(
            id=1, event_type="agent_start", timestamp=NAIVE,
        )

        assert _dump(model)["timestamp"].endswith("+00:00")

    def test_saved_config_timestamp_carries_utc(self):
        model = SavedConfigResponse(
            id=1, name="default", config_json={}, is_default=0, created_at=NAIVE,
        )

        assert _dump(model)["created_at"].endswith("+00:00")


@pytest.mark.unit
class TestEdgeCases:
    def test_none_stays_none(self):
        """An unstarted run has no started_at; it must not become an epoch."""
        model = RunResponse(
            id="x", ticker="HAL.NS", trade_date="2026-09-07",
            status="pending", created_at=NAIVE,
        )
        dumped = _dump(model)

        assert dumped["started_at"] is None
        assert dumped["completed_at"] is None

    def test_already_aware_value_is_not_shifted(self):
        """A tz-aware value must keep its instant, not be relabelled."""
        aware = NAIVE.replace(tzinfo=timezone.utc)
        model = RunListResponse(
            id="x", ticker="HAL.NS", trade_date="2026-09-07",
            status="running", created_at=aware,
        )

        assert _dump(model)["created_at"] == "2026-09-07T18:21:57.606176+00:00"

    def test_non_utc_aware_value_keeps_its_own_offset(self):
        """Stamping must not overwrite an offset that is already correct."""
        ist = timezone(timedelta(hours=5, minutes=30))
        model = RunListResponse(
            id="x", ticker="HAL.NS", trade_date="2026-09-07",
            status="running", created_at=NAIVE.replace(tzinfo=ist),
        )

        assert _dump(model)["created_at"].endswith("+05:30")


@pytest.mark.unit
class TestElapsedIsSane:
    def test_a_just_started_run_reads_as_seconds_not_hours(self):
        """The exact bug: elapsed came out as the viewer's UTC offset."""
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        model = RunResponse(
            id="x", ticker="RELIANCE.NS", trade_date="2026-09-07",
            status="running", created_at=started, started_at=started,
        )

        parsed = datetime.fromisoformat(_dump(model)["started_at"])
        elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()

        # A few seconds at most. Before the fix this was the UTC offset in
        # seconds — 19,800 for IST.
        assert 0 <= elapsed < 60
