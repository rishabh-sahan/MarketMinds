import { useEffect, useRef, useState, useCallback } from 'react';

const DEFAULT_WS_BASE = 'ws://localhost:8000/ws';
const WS_BASE = import.meta.env.VITE_WS_BASE || DEFAULT_WS_BASE;

/**
 * useWebSocket — connects to the run's WebSocket stream and collects events.
 * Returns { events, connected, error }.
 */
export function useWebSocket(runId) {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (!runId) return;

    const ws = new WebSocket(`${WS_BASE}/runs/${runId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'ping') return; // heartbeat
        setEvents((prev) => [...prev, event]);
      } catch {
        // ignore malformed
      }
    };

    ws.onerror = () => {
      setError('WebSocket error');
    };

    ws.onclose = () => {
      setConnected(false);
      // Attempt reconnect after 3s
      reconnectTimer.current = setTimeout(() => connect(), 3000);
    };
  }, [runId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, error, clearEvents };
}
