"""WebSocket endpoint for streaming run events to the frontend."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str):
    """Stream real-time events for a specific run.

    The client connects here after starting a run and receives JSON events:
    - agent_start, agent_complete, tool_call
    - log (info messages)
    - run_complete, run_error
    """
    await ws_manager.connect(run_id, ws)
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
