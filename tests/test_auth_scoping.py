"""Tests for who can see and modify which runs.

These pin the access rules themselves, not the JWT plumbing: token
verification is PyJWT's job and is stubbed here so the tests do not need a
live Supabase project or real key material. What is worth testing is the part
this project wrote — that one user cannot read, cancel, delete or export
another user's run, that a signed-out visitor sees only what was published,
and that an instance with no auth configured still behaves as it did before.

The last of those matters: authentication is opt-in, and the failure mode of
getting it wrong is either a locked-out developer or a silently open
deployment.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.auth as auth_module
from backend.database import Base, get_db
from backend.main import app
from backend.models import MemoryLogEntry, Run

ALICE = "user-alice"
BOB = "user-bob"


@pytest.fixture()
def db_session(tmp_path):
    """An isolated SQLite database per test, injected into the app."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.fixture()
def auth_on(monkeypatch):
    """Enable auth and accept a bearer token that is just a user id.

    Signature verification is PyJWT's responsibility and has its own tests
    upstream; stubbing the decode keeps these tests about authorisation.
    """
    monkeypatch.setattr(auth_module, "SUPABASE_URL", "https://project.supabase.co")

    def fake_decode(token: str) -> dict:
        if token.startswith("bad"):
            raise auth_module.jwt.InvalidTokenError("nope")
        return {"sub": token, "email": f"{token}@example.com", "user_metadata": {}}

    monkeypatch.setattr(auth_module, "_decode", fake_decode)


@pytest.fixture()
def client():
    return TestClient(app)


def _headers(user_id: str) -> dict:
    return {"Authorization": f"Bearer {user_id}"}


def _make_run(session, **kwargs) -> Run:
    run = Run(
        ticker=kwargs.pop("ticker", "HAL.NS"),
        trade_date=kwargs.pop("trade_date", "2026-09-04"),
        status=kwargs.pop("status", "completed"),
        result_json=kwargs.pop("result_json", {"market_report": "text"}),
        **kwargs,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


# --- Listing -------------------------------------------------------------


def test_list_returns_only_own_runs(client, db_session, auth_on):
    _make_run(db_session, user_id=ALICE, ticker="HAL.NS")
    _make_run(db_session, user_id=BOB, ticker="RELIANCE.NS")

    body = client.get("/api/runs", headers=_headers(ALICE)).json()

    assert [r["ticker"] for r in body] == ["HAL.NS"]


def test_signed_out_sees_only_public_runs(client, db_session, auth_on):
    _make_run(db_session, user_id=ALICE, ticker="HAL.NS")
    _make_run(db_session, user_id=ALICE, ticker="TCS.NS", is_public=1)

    body = client.get("/api/runs").json()

    assert [r["ticker"] for r in body] == ["TCS.NS"]


def test_owner_does_not_see_other_users_public_run(client, db_session, auth_on):
    """A published demo belongs on the signed-out page, not in someone's history."""
    _make_run(db_session, user_id=BOB, ticker="TCS.NS", is_public=1)
    _make_run(db_session, user_id=ALICE, ticker="HAL.NS")

    body = client.get("/api/runs", headers=_headers(ALICE)).json()

    assert [r["ticker"] for r in body] == ["HAL.NS"]


def test_expired_or_invalid_token_degrades_to_public_view(client, db_session, auth_on):
    """A stale session should show the public page, not an error."""
    _make_run(db_session, user_id=ALICE, ticker="HAL.NS")
    _make_run(db_session, user_id=ALICE, ticker="TCS.NS", is_public=1)

    response = client.get("/api/runs", headers=_headers("bad-token"))

    assert response.status_code == 200
    assert [r["ticker"] for r in response.json()] == ["TCS.NS"]


# --- Single run ----------------------------------------------------------


def test_cannot_read_another_users_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=BOB)

    response = client.get(f"/api/runs/{run.id}", headers=_headers(ALICE))

    # 404 rather than 403: a 403 would confirm the id exists.
    assert response.status_code == 404


def test_can_read_own_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=ALICE)

    assert client.get(f"/api/runs/{run.id}", headers=_headers(ALICE)).status_code == 200


def test_public_run_readable_signed_out(client, db_session, auth_on):
    run = _make_run(db_session, user_id=ALICE, is_public=1)

    assert client.get(f"/api/runs/{run.id}").status_code == 200


# --- Modification --------------------------------------------------------


def test_cannot_delete_another_users_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=BOB)

    response = client.delete(f"/api/runs/{run.id}", headers=_headers(ALICE))

    assert response.status_code == 404
    assert db_session.query(Run).filter(Run.id == run.id).first() is not None


def test_cannot_delete_a_public_run_you_do_not_own(client, db_session, auth_on):
    """Published for reading is not published for editing."""
    run = _make_run(db_session, user_id=BOB, is_public=1)

    response = client.delete(f"/api/runs/{run.id}", headers=_headers(ALICE))

    assert response.status_code == 404


def test_signed_out_cannot_delete_a_public_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=ALICE, is_public=1)

    # 401, not 404: with no credentials at all the honest answer is "sign in".
    # 404 is reserved for a *signed-in* caller asking about someone else's run,
    # where confirming the id exists would leak something.
    assert client.delete(f"/api/runs/{run.id}").status_code == 401
    assert db_session.query(Run).filter(Run.id == run.id).first() is not None


def test_cannot_cancel_another_users_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=BOB, status="running")

    response = client.post(f"/api/runs/{run.id}/cancel", headers=_headers(ALICE))

    assert response.status_code == 404


def test_owner_can_delete_own_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=ALICE)

    response = client.delete(f"/api/runs/{run.id}", headers=_headers(ALICE))

    assert response.status_code == 204


# --- Export --------------------------------------------------------------


def test_cannot_export_another_users_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=BOB)

    assert client.get(f"/api/runs/{run.id}/export", headers=_headers(ALICE)).status_code == 404


def test_signed_out_cannot_export_a_private_run(client, db_session, auth_on):
    run = _make_run(db_session, user_id=ALICE)

    assert client.get(f"/api/runs/{run.id}/export").status_code == 404


# --- Stats ---------------------------------------------------------------


def test_stats_count_only_own_runs(client, db_session, auth_on):
    _make_run(db_session, user_id=ALICE, llm_calls=3)
    _make_run(db_session, user_id=BOB, llm_calls=99)

    body = client.get("/api/runs/stats", headers=_headers(ALICE)).json()

    assert body["total"] == 1
    assert body["llm_calls"] == 3


# --- Memory --------------------------------------------------------------


def _make_memory(session, user_id, ticker="HAL.NS"):
    entry = MemoryLogEntry(
        user_id=user_id,
        ticker=ticker,
        trade_date="2026-09-04",
        rating="Buy",
        decision="Buy on strong order book.",
    )
    session.add(entry)
    session.commit()
    return entry


def test_memory_page_shows_only_own_entries(client, db_session, auth_on):
    _make_memory(db_session, ALICE, "HAL.NS")
    _make_memory(db_session, BOB, "RELIANCE.NS")

    body = client.get("/api/memory", headers=_headers(ALICE)).json()

    assert [e["ticker"] for e in body["entries"]] == ["HAL.NS"]


def test_memory_reports_shared_pool_size(client, db_session, auth_on):
    """A user seeing 1 of 2 entries should be told the pool is larger."""
    _make_memory(db_session, ALICE)
    _make_memory(db_session, BOB)

    body = client.get("/api/memory", headers=_headers(ALICE)).json()

    assert body["total"] == 1
    assert body["pool_total"] == 2


def test_agents_read_the_whole_pool(db_session):
    """Writes are scoped to a user; reads deliberately are not.

    This is the mechanism behind 'shared read, private write' — if it ever
    started filtering by user, every new user's first runs would silently
    lose the benefit of the pool.
    """
    from backend.services.db_memory import DatabaseMemoryLog

    _make_memory(db_session, ALICE, "HAL.NS")
    _make_memory(db_session, BOB, "RELIANCE.NS")

    log = DatabaseMemoryLog(lambda: db_session, user_id=ALICE)

    assert {e["ticker"] for e in log.load_entries()} == {"HAL.NS", "RELIANCE.NS"}


# --- Auth disabled -------------------------------------------------------


def test_without_supabase_everything_is_visible(client, db_session, monkeypatch):
    """A local checkout keeps working exactly as it did before auth existed."""
    monkeypatch.setattr(auth_module, "SUPABASE_URL", "")
    _make_run(db_session, user_id=None, ticker="HAL.NS")
    _make_run(db_session, user_id=BOB, ticker="RELIANCE.NS")

    body = client.get("/api/runs").json()

    assert {r["ticker"] for r in body} == {"HAL.NS", "RELIANCE.NS"}


def test_without_supabase_delete_is_allowed(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_module, "SUPABASE_URL", "")
    run = _make_run(db_session, user_id=None)

    assert client.delete(f"/api/runs/{run.id}").status_code == 204


def test_auth_config_reports_disabled_without_supabase(client, monkeypatch):
    monkeypatch.setattr(auth_module, "SUPABASE_URL", "")

    body = client.get("/api/auth/config").json()

    assert body["enabled"] is False
    assert body["url"] is None


# --- Signed-out showcase --------------------------------------------------


@pytest.mark.unit
class TestDemoShowcase:
    """The signed-out dashboard shows published runs, varied per visitor.

    The rule that matters most is the negative one: whatever the seed, the
    showcase must never surface a run its owner did not publish. Everything
    else here is presentation.
    """

    def _publish(self, session, n):
        for i in range(n):
            _make_run(session, user_id=ALICE, ticker=f"PUB{i}.NS", is_public=1)

    def test_never_includes_a_private_run(self, client, db_session, auth_on):
        self._publish(db_session, 3)
        _make_run(db_session, user_id=BOB, ticker="SECRET.NS")

        seen = set()
        for seed in ("a", "b", "c", "d", "e", "f", "g", "h"):
            body = client.get(f"/api/runs?seed={seed}").json()
            seen.update(r["ticker"] for r in body)

        assert "SECRET.NS" not in seen
        assert seen == {"PUB0.NS", "PUB1.NS", "PUB2.NS"}

    def test_same_seed_is_stable_across_requests(self, client, db_session, auth_on):
        """A reload must not reshuffle the cards under the visitor."""
        self._publish(db_session, 5)

        first = [r["id"] for r in client.get("/api/runs?seed=steady").json()]
        second = [r["id"] for r in client.get("/api/runs?seed=steady").json()]

        assert first == second

    def test_different_seeds_give_different_orders(self, client, db_session, auth_on):
        self._publish(db_session, 6)

        orders = {
            tuple(r["id"] for r in client.get(f"/api/runs?seed={s}").json())
            for s in ("alpha", "beta", "gamma", "delta", "epsilon")
        }

        # Five seeds over six runs should not all collapse to one ordering.
        assert len(orders) > 1

    def test_missing_seed_still_returns_the_showcase(self, client, db_session, auth_on):
        self._publish(db_session, 3)

        body = client.get("/api/runs").json()

        assert len(body) == 3

    def test_empty_pool_returns_empty_not_an_error(self, client, db_session, auth_on):
        _make_run(db_session, user_id=ALICE, ticker="PRIVATE.NS")

        response = client.get("/api/runs?seed=x")

        assert response.status_code == 200
        assert response.json() == []

    def test_stats_describe_the_same_selection(self, client, db_session, auth_on):
        """Counters that disagree with the visible list read as a bug."""
        self._publish(db_session, 4)
        _make_run(db_session, user_id=BOB, ticker="SECRET.NS", llm_calls=999)

        listed = client.get("/api/runs?seed=zz").json()
        stats = client.get("/api/runs/stats?seed=zz").json()

        assert stats["total"] == len(listed)
        assert stats["llm_calls"] != 999

    def test_signed_in_user_is_unaffected_by_a_seed(self, client, db_session, auth_on):
        """A seed must not shuffle or truncate somebody's own history."""
        _make_run(db_session, user_id=ALICE, ticker="MINE.NS")
        self._publish(db_session, 2)

        body = client.get("/api/runs?seed=whatever", headers=_headers(ALICE)).json()

        # Alice owns her own run plus the two she published.
        assert {r["ticker"] for r in body} == {"MINE.NS", "PUB0.NS", "PUB1.NS"}
