# syntax=docker/dockerfile:1

# =============================================================================
# MarketMinds — single image running both the API and the web UI.
#
# The React app is compiled to static files in the first stage, then served by
# the same FastAPI process that answers /api and /ws in the second. One
# process, one port, no CORS, no reverse proxy: `docker run` gives you the
# whole application.
# =============================================================================


# --- Stage 1: build the frontend --------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /build

# Dependencies first, so editing application source does not reinstall them.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# No VITE_API_BASE / VITE_WS_BASE: the app calls its own origin, which is what
# lets one build work behind localhost, a container, or a TLS proxy alike.
RUN npm run build


# --- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The only OS package needed: a Unicode font. ReportLab's built-ins predate the
# rupee sign (U+20B9), so without this every price in a PDF renders as a black
# box. ~1.5MB, and it keeps the export legible for an Indian market tool.
RUN apt-get update     && apt-get install -y --no-install-recommends fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*

# Python dependencies. `pip install .` reads pyproject.toml, so the packages it
# declares must be present; backend/requirements.txt adds the web server.
# Application code that changes often (backend/) is copied afterwards so this
# layer stays cached.
COPY pyproject.toml README.md ./
COPY backend/requirements.txt ./backend/requirements.txt
COPY marketminds/ ./marketminds/
COPY cli/ ./cli/
RUN pip install --no-cache-dir . -r backend/requirements.txt

# Application code and the compiled UI.
COPY backend/ ./backend/
COPY --from=frontend /build/dist/ ./frontend/dist/

# All mutable state lives under /data so a single volume persists everything:
# the run database, the decision log the agents learn from, cached market data
# and checkpoints.
ENV MARKETMINDS_DB_PATH=/data/marketminds.db \
    MARKETMINDS_RESULTS_DIR=/data/logs \
    MARKETMINDS_CACHE_DIR=/data/cache \
    MARKETMINDS_MEMORY_LOG_PATH=/data/memory/trading_memory.md \
    MARKETMINDS_FRONTEND_DIST=/app/frontend/dist \
    PORT=8000

# Run unprivileged. /data is created and owned here so a named volume inherits
# that ownership on first use.
RUN useradd --create-home --uid 10001 marketminds \
    && mkdir -p /data/logs /data/cache /data/memory \
    && chown -R marketminds:marketminds /app /data
USER marketminds

VOLUME ["/data"]
EXPOSE 8000

# A run in flight is a long HTTP-free stretch, so the check hits the API rather
# than assuming traffic. urllib avoids adding curl to the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health',timeout=4)" || exit 1

# `exec` so uvicorn is PID 1's direct child and receives SIGTERM on stop.
# No --reload: it would restart the server mid-analysis and lose the run.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
