"""WebSocket connection manager — tracks active connections per run_id."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections and broadcasts events to subscribers."""

    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(run_id, []).append(ws)
        logger.info("WS connected for run %s (total: %d)", run_id, len(self._connections[run_id]))

    async def disconnect(self, run_id: str, ws: WebSocket):
        async with self._lock:
            conns = self._connections.get(run_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(run_id, None)

    async def broadcast(self, run_id: str, event: dict):
        """Send an event dict to all subscribers of a run."""
        async with self._lock:
            conns = list(self._connections.get(run_id, []))

        dead = []
        payload = json.dumps(event, default=str)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up broken connections
        if dead:
            async with self._lock:
                for ws in dead:
                    conns = self._connections.get(run_id, [])
                    if ws in conns:
                        conns.remove(ws)

    async def emit_agent_start(self, run_id: str, agent_name: str):
        await self.broadcast(run_id, {
            "type": "agent_start",
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_agent_complete(self, run_id: str, agent_name: str, report_key: str = None, report_content: str = None):
        event = {
            "type": "agent_complete",
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if report_key and report_content:
            event["report_key"] = report_key
            event["report_content"] = report_content
        await self.broadcast(run_id, event)

    async def emit_tool_call(self, run_id: str, agent_name: str, tool_name: str, args: dict = None):
        await self.broadcast(run_id, {
            "type": "tool_call",
            "agent": agent_name,
            "tool": tool_name,
            "args": args or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_report_update(self, run_id: str, agent_name: str, report_key: str, report_content: str):
        """Push a report section as soon as the agent that owns it produces text."""
        await self.broadcast(run_id, {
            "type": "report_update",
            "agent": agent_name,
            "report_key": report_key,
            "report_content": report_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_agent_snapshot(self, run_id: str, statuses: dict):
        """Push the whole pipeline state, so a late subscriber catches up at once."""
        await self.broadcast(run_id, {
            "type": "agent_snapshot",
            "statuses": statuses,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_stats(self, run_id: str, stats: dict):
        await self.broadcast(run_id, {
            "type": "stats",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_status(self, run_id: str, status: str):
        await self.broadcast(run_id, {
            "type": "run_status",
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_run_cancelled(self, run_id: str):
        await self.broadcast(run_id, {
            "type": "run_cancelled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_run_complete(self, run_id: str, decision: str):
        await self.broadcast(run_id, {
            "type": "run_complete",
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_run_error(self, run_id: str, error: str):
        await self.broadcast(run_id, {
            "type": "run_error",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_log(self, run_id: str, message: str, level: str = "info"):
        await self.broadcast(run_id, {
            "type": "log",
            "message": message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Global singleton
ws_manager = WSManager()
