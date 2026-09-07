"""Copy existing MarketMinds history into a PostgreSQL database.

Run once when moving from local SQLite to a deployed Postgres instance. It
carries over what would otherwise be lost:

  * runs, with their reports, config snapshots and usage counters
  * the events behind each run's live log
  * the markdown decision log, turned into `memory_entries` rows

Usage
-----

    # Where the data is going. From Supabase: Project Settings > Database >
    # Connection string > URI, with your database password substituted in.
    export DATABASE_URL='postgresql://postgres:PASSWORD@db.<ref>.supabase.co:5432/postgres'

    python scripts/migrate_to_postgres.py --source backend/marketminds.db

    # Preview without writing anything
    python scripts/migrate_to_postgres.py --source backend/marketminds.db --dry-run

    # Attribute the migrated rows to a signed-in account, and publish one run
    # as the demo signed-out visitors see
    python scripts/migrate_to_postgres.py \
        --source backend/marketminds.db \
        --user-id 0f9c... --public-run a4c8000c7b154f21aefd960e2b3dc2cb

Safe to re-run: rows whose ids already exist in the target are skipped rather
than duplicated or overwritten, so an interrupted migration can simply be
started again.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# Import the application's own models so the migration cannot drift from the
# schema the app expects.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.models import MemoryLogEntry, Run, RunEvent  # noqa: E402


def _parse_dt(value) -> Optional[datetime]:
    """SQLite hands back naive ISO strings; Postgres wants datetimes."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # The columns are TIMESTAMP WITHOUT TIME ZONE, so an offset-aware value
    # would be rejected. Everything is written in UTC, so drop the offset.
    return parsed.replace(tzinfo=None)


def _parse_json(value):
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _pct_to_float(value: Optional[str]) -> Optional[float]:
    """'+3.2%' -> 0.032"""
    if not value:
        return None
    text = str(value).strip().rstrip("%")
    try:
        return float(text) / 100.0
    except ValueError:
        return None


def _days_to_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    text = str(value).strip().rstrip("d")
    try:
        return int(text)
    except ValueError:
        return None


def _rows(conn: sqlite3.Connection, table: str) -> Iterable[sqlite3.Row]:
    cursor = conn.execute(f"SELECT * FROM {table}")
    cursor.row_factory = sqlite3.Row
    conn.row_factory = sqlite3.Row
    return conn.execute(f"SELECT * FROM {table}").fetchall()


def migrate_runs(source: sqlite3.Connection, session, user_id, public_run, dry_run):
    existing = {r[0] for r in session.query(Run.id).all()}
    copied = skipped = 0

    for row in _rows(source, "runs"):
        if row["id"] in existing:
            skipped += 1
            continue
        run = Run(
            id=row["id"],
            # Rows predating authentication have no owner. Assigning one is
            # opt-in rather than guessed: an unowned run is invisible, which
            # is recoverable; attributing it to the wrong account is not.
            user_id=user_id,
            is_public=1 if public_run and row["id"] == public_run else 0,
            ticker=row["ticker"],
            trade_date=row["trade_date"],
            status=row["status"],
            config_snapshot=_parse_json(row["config_snapshot"]),
            final_decision=row["final_decision"],
            result_json=_parse_json(row["result_json"]),
            error_message=row["error_message"],
            agent_status=_parse_json(row["agent_status"]),
            llm_calls=row["llm_calls"] or 0,
            tool_calls=row["tool_calls"] or 0,
            tokens_in=row["tokens_in"] or 0,
            tokens_out=row["tokens_out"] or 0,
            created_at=_parse_dt(row["created_at"]),
            started_at=_parse_dt(row["started_at"]),
            completed_at=_parse_dt(row["completed_at"]),
        )
        if not dry_run:
            session.add(run)
        copied += 1

    return copied, skipped


def migrate_events(source: sqlite3.Connection, session, dry_run):
    # Events have autoincrement ids that mean nothing across databases, so
    # they are matched on their content instead: a run that already has events
    # is left alone rather than gaining a second copy of each.
    runs_with_events = {
        r[0] for r in session.query(RunEvent.run_id).distinct().all()
    }
    copied = skipped = 0

    for row in _rows(source, "run_events"):
        if row["run_id"] in runs_with_events:
            skipped += 1
            continue
        event = RunEvent(
            run_id=row["run_id"],
            agent_name=row["agent_name"],
            event_type=row["event_type"],
            payload=_parse_json(row["payload"]),
            timestamp=_parse_dt(row["timestamp"]),
        )
        if not dry_run:
            session.add(event)
        copied += 1

    return copied, skipped


def migrate_memory_rows(source: sqlite3.Connection, session, user_id, dry_run):
    """Copy `memory_entries` rows the local database already holds.

    Separate from the markdown import below: once a local instance has run
    against the database-backed decision log, entries live in this table, and
    reading only the markdown file would silently leave them behind.
    """
    try:
        rows = _rows(source, "memory_entries")
    except sqlite3.OperationalError:
        return 0, 0  # older local database, no such table

    existing = {
        (t, d) for t, d in session.query(
            MemoryLogEntry.ticker, MemoryLogEntry.trade_date
        ).all()
    }
    copied = skipped = 0

    for row in rows:
        key = (row["ticker"], row["trade_date"])
        if key in existing:
            skipped += 1
            continue
        session_row = MemoryLogEntry(
            user_id=user_id or row["user_id"],
            ticker=row["ticker"],
            trade_date=row["trade_date"],
            rating=row["rating"],
            decision=row["decision"] or "",
            raw_return=row["raw_return"],
            alpha_return=row["alpha_return"],
            holding_days=row["holding_days"],
            reflection=row["reflection"],
            created_at=_parse_dt(row["created_at"]),
            resolved_at=_parse_dt(row["resolved_at"]),
        )
        if not dry_run:
            session.add(session_row)
        existing.add(key)
        copied += 1

    return copied, skipped


def migrate_memory(log_path: Path, session, user_id, dry_run):
    """Turn the markdown decision log into rows."""
    from marketminds.agents.utils.memory import TradingMemoryLog

    if not log_path.exists():
        return 0, 0

    entries = TradingMemoryLog({"memory_log_path": str(log_path)}).load_entries()

    existing = {
        (t, d) for t, d in session.query(
            MemoryLogEntry.ticker, MemoryLogEntry.trade_date
        ).all()
    }
    copied = skipped = 0

    for entry in entries:
        key = (entry.get("ticker"), entry.get("date"))
        if key in existing:
            skipped += 1
            continue
        pending = entry.get("pending")
        row = MemoryLogEntry(
            user_id=user_id,
            ticker=entry.get("ticker") or "",
            trade_date=entry.get("date") or "",
            rating=entry.get("rating"),
            decision=entry.get("decision") or "",
            reflection=entry.get("reflection") or None,
            raw_return=None if pending else _pct_to_float(entry.get("raw")),
            alpha_return=None if pending else _pct_to_float(entry.get("alpha")),
            holding_days=None if pending else _days_to_int(entry.get("holding")),
            # A resolved entry needs a resolved_at: it is the only marker
            # distinguishing the two states, and a resolved entry left NULL
            # would be handed to a later run as unfinished work.
            resolved_at=None if pending else datetime.utcnow(),
        )
        if not dry_run:
            session.add(row)
        existing.add(key)
        copied += 1

    return copied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default="backend/marketminds.db",
        help="SQLite database to read (default: backend/marketminds.db)",
    )
    parser.add_argument(
        "--memory-log", default=None,
        help="Markdown decision log to import (default: the configured path)",
    )
    parser.add_argument(
        "--user-id", default=None,
        help="Supabase user id to attribute migrated rows to. Without it the "
             "rows are unowned, and therefore invisible on an authenticated "
             "instance until claimed.",
    )
    parser.add_argument(
        "--public-run", default=None,
        help="Run id to publish as the demo signed-out visitors can read.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be copied without writing anything.",
    )
    args = parser.parse_args()

    # Read .env too, so the connection string (which carries the database
    # password) can live in the gitignored file rather than being typed into a
    # shell where it lands in history.
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

    target_url = os.getenv("DATABASE_URL", "").strip()
    if not target_url:
        print(
            "DATABASE_URL is not set. Add it to .env or export it, then re-run.",
            file=sys.stderr,
        )
        return 2
    if target_url.startswith("postgres://"):
        target_url = "postgresql://" + target_url[len("postgres://"):]
    if target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgresql://"):]

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"No SQLite database at {source_path}", file=sys.stderr)
        return 2

    if args.memory_log:
        log_path = Path(args.memory_log)
    else:
        from marketminds.default_config import DEFAULT_CONFIG
        log_path = Path(DEFAULT_CONFIG["memory_log_path"])

    print(f"source : {source_path}")
    print(f"memory : {log_path}")
    print(f"target : {target_url.split('@')[-1]}")  # never print the password
    if args.dry_run:
        print("mode   : DRY RUN, nothing will be written")
    print()

    source = sqlite3.connect(str(source_path))
    source.row_factory = sqlite3.Row

    engine = create_engine(target_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()

    try:
        runs_copied, runs_skipped = migrate_runs(
            source, session, args.user_id, args.public_run, args.dry_run
        )
        # Runs must land before their events: the foreign key depends on it.
        if not args.dry_run:
            session.flush()

        events_copied, events_skipped = migrate_events(source, session, args.dry_run)

        # Table rows first, then the markdown log. Both write into
        # memory_entries and dedupe on (ticker, trade_date), so whichever runs
        # first wins — and the table rows are the richer, more recent form.
        rows_copied, rows_skipped = migrate_memory_rows(
            source, session, args.user_id, args.dry_run
        )
        log_copied, log_skipped = migrate_memory(
            log_path, session, args.user_id, args.dry_run
        )
        memory_copied = rows_copied + log_copied
        memory_skipped = rows_skipped + log_skipped

        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        source.close()
        engine.dispose()

    print(f"runs      copied {runs_copied:>4}   already present {runs_skipped}")
    print(f"events    copied {events_copied:>4}   already present {events_skipped}")
    print(f"memory    copied {memory_copied:>4}   already present {memory_skipped}")

    if not args.user_id and (runs_copied or memory_copied):
        print()
        print("Note: migrated with no --user-id, so these rows have no owner and")
        print("will not appear for any signed-in user. Re-run with --user-id, or")
        print("claim them with:")
        print("  UPDATE runs SET user_id = '<id>' WHERE user_id IS NULL;")
        print("  UPDATE memory_entries SET user_id = '<id>' WHERE user_id IS NULL;")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
