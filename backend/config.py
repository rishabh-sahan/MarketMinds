"""Backend configuration — DB URL, paths, and runtime settings."""

import os
from pathlib import Path

# Project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# SQLite database — stored alongside the project for easy dev setup
DATABASE_PATH = os.getenv(
    "TRADINGAGENTS_DB_PATH",
    str(PROJECT_ROOT / "backend" / "tradingagents.db"),
)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# CORS — frontend dev server origin
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://tradingagents-frontend-q1km.onrender.com")

# Backend port
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
