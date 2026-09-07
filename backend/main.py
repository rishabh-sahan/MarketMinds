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
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIST, FRONTEND_URL
from backend.database import create_tables
from backend.services.run_service import set_ws_loop

logger = logging.getLogger(__name__)

from backend.routers import runs, config, providers, memory
from backend.auth import warn_if_open
from backend.routers import auth as auth_router
from backend.ws.stream import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    set_ws_loop(asyncio.get_running_loop())
    create_tables()
    warn_if_open()
    yield


app = FastAPI(
    title="MarketMinds API",
    description="REST + WebSocket API for the MarketMinds multi-agent trading framework",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — the deployed frontend origin, plus any local dev server. Vite moves to
# the next free port when 5173 is taken, so pinning a single port makes the API
# unreachable for no good reason; the regex covers localhost on any port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(runs.router)
app.include_router(config.router)
app.include_router(providers.router)
app.include_router(memory.router)
app.include_router(auth_router.router)
app.include_router(ws_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "marketminds-api"}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
# When a built frontend is present (the Docker image bakes one in), this same
# process serves it, so the whole app runs on one port with no CORS involved.
# Without a build — the usual local setup — these routes are simply absent and
# Vite serves the UI on its own port instead.

if FRONTEND_DIST.is_dir():
    _assets = FRONTEND_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    _index = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve a built file when one matches, otherwise the SPA entry point.

        Registered last, so every API and WebSocket route is matched first. The
        `/api` and `/ws` prefixes still 404 as JSON rather than falling through
        to the HTML shell, which would otherwise hand API clients a 200 and a
        page of markup for a mistyped endpoint.
        """
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")

        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            # Containment check: a crafted path must not escape the build dir.
            if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
                return FileResponse(candidate)

        # Unknown paths are client-side routes; React Router resolves them.
        return FileResponse(_index)

    logger.info("Serving frontend from %s", FRONTEND_DIST)
else:
    logger.info(
        "No frontend build at %s — API only. Run the Vite dev server for the UI.",
        FRONTEND_DIST,
    )
