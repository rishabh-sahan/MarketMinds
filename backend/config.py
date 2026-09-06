"""Backend configuration — DB URL, paths, and runtime settings."""

import os
from pathlib import Path

# Project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# SQLite database — stored alongside the project for easy dev setup
DATABASE_PATH = os.getenv(
    "MARKETMINDS_DB_PATH",
    str(PROJECT_ROOT / "backend" / "marketminds.db"),
)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

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
