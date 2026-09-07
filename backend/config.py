"""Backend configuration — DB URL, paths, and runtime settings."""

import os
from pathlib import Path

# Project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Database. SQLite by default — one file, no server, right for local use.
# A deployed instance should set DATABASE_URL to a PostgreSQL DSN instead:
# container disks are usually ephemeral, and SQLite cannot be shared between
# processes.
DATABASE_PATH = os.getenv(
    "MARKETMINDS_DB_PATH",
    str(PROJECT_ROOT / "backend" / "marketminds.db"),
)


def _database_url() -> str:
    """Resolve the connection URL, normalising the DSN hosts hand out.

    Managed providers (Render, Heroku, Railway) still emit ``postgres://``,
    a scheme SQLAlchemy dropped support for; and the default driver for
    ``postgresql://`` is psycopg2, while this project installs psycopg 3.
    Both are corrected here so a pasted DSN simply works.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DATABASE_PATH}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()

# CORS — additional allowed origin for a deployed frontend. The local Vite
# dev origins are always allowed (see backend/main.py).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Built frontend to serve from this process. Present in the Docker image and
# after a local `npm run build`; absent during normal development, where Vite
# serves the UI itself.
FRONTEND_DIST = Path(
    os.getenv("MARKETMINDS_FRONTEND_DIST", str(PROJECT_ROOT / "frontend" / "dist"))
)

# Backend port
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
