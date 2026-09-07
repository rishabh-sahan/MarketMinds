"""WebSocket endpoint for streaming run events to the frontend."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.auth import AuthUser, auth_enabled
from backend.database import SessionLocal
from backend.models import Run
from backend.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Closure codes. 1008 is "policy violation", the closest thing the WebSocket
# protocol has to 401/403 — there is no status code in a rejected handshake.
_POLICY_VIOLATION = 1008


def _token_from_subprotocols(ws: WebSocket) -> Tuple[Optional[str], Optional[str]]:
    """Pull a bearer token out of the requested WebSocket subprotocols.

    A browser cannot set an Authorization header on a WebSocket, so the token
    has to travel some other way. The usual shortcut is a query parameter,
    which puts a live credential into every proxy and access log that records
    request lines. The subprotocol list is not logged that way, and a JWT is
    made of characters a subprotocol value permits, so the client offers
    ``['bearer', <token>]`` and we echo back ``bearer``.

    Returns (token, subprotocol_to_echo).
    """
    header = ws.headers.get("sec-websocket-protocol")
    if not header:
        return None, None
    offered = [part.strip() for part in header.split(",") if part.strip()]
    if len(offered) >= 2 and offered[0] == "bearer":
        return offered[1], "bearer"
    return None, offered[0] if offered else None


def _authorise(run_id: str, token: Optional[str]) -> bool:
    """Whether this token may stream this run.

    Mirrors the REST rule exactly: your own run, or one published as a public
    demo. Run ids are unguessable, but an unguessable identifier is not access
    control — a link pasted anywhere would otherwise expose a live analysis.
    """
    if not auth_enabled():
        return True

    from backend.auth import _decode  # local import keeps module import cheap

    user_id = None
    if token:
        try:
            user_id = AuthUser(_decode(token)).id
        except Exception as exc:
            logger.info("WS token rejected for run %s: %s", run_id, exc)

    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run is None:
            return False
        if run.is_public:
            return True
        return user_id is not None and run.user_id == user_id
    finally:
        db.close()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str):
    """Stream real-time events for a specific run.

    The client connects here after starting a run and receives JSON events:
    - agent_start, agent_complete, tool_call
    - log (info messages)
    - run_complete, run_error
    """
    token, subprotocol = _token_from_subprotocols(ws)

    if not _authorise(run_id, token):
        # Closed before accept: the handshake never completes, so nothing is
        # streamed to a client that should not see it.
        await ws.close(code=_POLICY_VIOLATION)
        return

    await ws_manager.connect(run_id, ws, subprotocol=subprotocol)
    try:
        # Keep connection alive — wait for client disconnect
        while True:
            # Heartbeat: if client sends anything, just ignore
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat ping
                try:
                    await ws.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(run_id, ws)
