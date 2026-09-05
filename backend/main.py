"""FastAPI application — main entry point for the backend server."""

from __future__ import annotations

import sys
import os
from contextlib import asynccontextmanager

# Ensure the project root is on sys.path so `marketminds` and `backend` are importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import FRONTEND_URL
from backend.database import create_tables
from backend.services.run_service import set_ws_loop

from backend.routers import runs, config, providers
from backend.ws.stream import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    set_ws_loop(asyncio.get_running_loop())
    create_tables()
    yield


app = FastAPI(
    title="MarketMinds API",
    description="REST + WebSocket API for the MarketMinds multi-agent trading framework",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(runs.router)
app.include_router(config.router)
app.include_router(providers.router)
app.include_router(ws_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "marketminds-api"}
