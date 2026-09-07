import { useCallback, useEffect, useReducer, useRef } from 'react';
import { authToken } from '../lib/api';

/**
 * The socket lives on the same origin as the page, so its URL is derived from
 * `window.location` rather than pinned to a port — that keeps one build
 * working behind localhost, a container, or a TLS reverse proxy alike.
 * Set VITE_WS_BASE only when the API is deployed on a separate origin.
 */
function defaultWsBase() {
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws`;
}

const WS_BASE = import.meta.env.VITE_WS_BASE || defaultWsBase();

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

/** Cap the in-memory log so a long run cannot grow the tab without bound. */
const MAX_LOG = 500;

const initialState = {
  connected: false,
  status: null,          // pending | running | completed | failed | cancelled
  agentStatus: {},       // agent name -> pending | running | completed
  reports: {},           // report key -> markdown, as each agent produces it
  activeReportKey: null, // the section that most recently changed
  log: [],
  stats: { llm_calls: 0, tool_calls: 0, tokens_in: 0, tokens_out: 0 },
  decision: null,
  error: null,
};

function appendLog(log, entry) {
  const next = [...log, entry];
  return next.length > MAX_LOG ? next.slice(next.length - MAX_LOG) : next;
}

function reducer(state, action) {
  switch (action.type) {
    case 'connected':
      return { ...state, connected: action.value };

    // Seed from the REST payload so a page opened mid-run — or after a
    // refresh — shows real progress instead of an empty pipeline.
    case 'hydrate': {
      const { run } = action;
      const reports = { ...state.reports };
      const log = [];

      for (const event of run.events || []) {
        if (event.event_type === 'report_update' && event.payload?.report_key) {
          reports[event.payload.report_key] = event.payload.report_content || '';
        }
        log.push({
          type: event.event_type,
          agent: event.agent_name,
          tool: event.payload?.tool,
          args: event.payload?.args,
          message: event.payload?.error || event.payload?.message,
          decision: event.payload?.decision,
          timestamp: event.timestamp,
        });
      }

      return {
        ...state,
        status: run.status,
        agentStatus: { ...(run.agent_status || {}), ...state.agentStatus },
        reports: { ...reports, ...state.reports },
        log: state.log.length ? state.log : log.slice(-MAX_LOG),
        stats: {
          llm_calls: run.llm_calls || 0,
          tool_calls: run.tool_calls || 0,
          tokens_in: run.tokens_in || 0,
          tokens_out: run.tokens_out || 0,
        },
        decision: run.final_decision || state.decision,
        error: run.error_message || state.error,
      };
    }

    case 'event': {
      const event = action.event;
      const next = { ...state };

      switch (event.type) {
        case 'agent_snapshot':
          next.agentStatus = { ...next.agentStatus, ...(event.statuses || {}) };
          return next;

        case 'stats':
          next.stats = { ...next.stats, ...(event.stats || {}) };
          return next;

        case 'run_status':
          next.status = event.status;
          return next;

        case 'agent_start':
        case 'agent_complete':
          next.agentStatus = {
            ...next.agentStatus,
            [event.agent]: event.type === 'agent_start' ? 'running' : 'completed',
          };
          next.log = appendLog(next.log, event);
          return next;

        case 'report_update':
          next.reports = { ...next.reports, [event.report_key]: event.report_content };
          next.activeReportKey = event.report_key;
          // Report text is large and arrives repeatedly; it belongs in the
          // report pane, not the log stream.
          return next;

        case 'run_complete':
          next.status = 'completed';
          next.decision = event.decision;
          next.log = appendLog(next.log, event);
          return next;

        case 'run_error':
          next.status = 'failed';
          next.error = event.error;
          next.log = appendLog(next.log, event);
          return next;

        case 'run_cancelled':
          next.status = 'cancelled';
          next.log = appendLog(next.log, event);
          return next;

        case 'tool_call':
        case 'log':
          next.log = appendLog(next.log, event);
          return next;

        default:
          return state;
      }
    }

    default:
      return state;
  }
}

/**
 * Subscribe to a run's live event stream.
 *
 * The socket is the source of truth while a run is in flight; `hydrate` seeds
 * the same shape from the REST payload so the view is correct on first paint
 * and after a reconnect. Once the run reaches a terminal status the socket is
 * closed and not retried — there is nothing further to receive.
 */
export function useRunStream(runId, { enabled = true } = {}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef(null);
  const retryRef = useRef(null);
  const attemptsRef = useRef(0);
  const statusRef = useRef(null);

  // Kept in a ref so the socket callbacks can read the current status without
  // re-subscribing on every status change.
  useEffect(() => {
    statusRef.current = state.status;
  }, [state.status]);

  const hydrate = useCallback((run) => dispatch({ type: 'hydrate', run }), []);

  useEffect(() => {
    if (!runId || !enabled) return undefined;

    let closed = false;

    const connect = () => {
      if (closed || TERMINAL.has(statusRef.current)) return;

      let ws;
      try {
        // A WebSocket cannot carry an Authorization header, and putting the
        // token in the query string would write a live credential into every
        // proxy and access log. The subprotocol list is not logged that way,
        // so the token rides there and the server echoes back 'bearer'.
        const token = authToken();
        ws = token
          ? new WebSocket(`${WS_BASE}/runs/${runId}`, ['bearer', token])
          : new WebSocket(`${WS_BASE}/runs/${runId}`);
      } catch {
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        attemptsRef.current = 0;
        dispatch({ type: 'connected', value: true });
      };

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          if (event.type === 'ping') return; // server heartbeat
          dispatch({ type: 'event', event });
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = () => {
        dispatch({ type: 'connected', value: false });
        if (closed || TERMINAL.has(statusRef.current)) return;
        // Back off so a server that is down does not get hammered, but stay
        // responsive for the common case of a quick restart.
        const delay = Math.min(1000 * 2 ** attemptsRef.current, 15000);
        attemptsRef.current += 1;
        retryRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      closed = true;
      clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [runId, enabled]);

  // Terminal runs have nothing left to stream — drop the socket immediately
  // rather than holding it open until unmount.
  useEffect(() => {
    if (TERMINAL.has(state.status)) wsRef.current?.close();
  }, [state.status]);

  return { ...state, hydrate, isTerminal: TERMINAL.has(state.status) };
}

export { TERMINAL as TERMINAL_STATUSES };
