import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRun } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import ReactMarkdown from 'react-markdown';
import './LiveViewer.css';

const AGENT_PIPELINE = [
  { name: 'Market Analyst', phase: 'Analysis', icon: '📊' },
  { name: 'Sentiment Analyst', phase: 'Analysis', icon: '💬' },
  { name: 'News Analyst', phase: 'Analysis', icon: '📰' },
  { name: 'Fundamentals Analyst', phase: 'Analysis', icon: '📈' },
  { name: 'Bull Researcher', phase: 'Research', icon: '🐂' },
  { name: 'Bear Researcher', phase: 'Research', icon: '🐻' },
  { name: 'Research Manager', phase: 'Research', icon: '🧠' },
  { name: 'Trader', phase: 'Trading', icon: '💰' },
  { name: 'Aggressive Analyst', phase: 'Risk', icon: '🔥' },
  { name: 'Conservative Analyst', phase: 'Risk', icon: '🛡️' },
  { name: 'Neutral Analyst', phase: 'Risk', icon: '⚖️' },
  { name: 'Portfolio Manager', phase: 'Decision', icon: '👔' },
];

export default function LiveViewer() {
  const { runId } = useParams();
  const { events, connected } = useWebSocket(runId);
  const [run, setRun] = useState(null);
  const [activeAgents, setActiveAgents] = useState(new Set());
  const [completedAgents, setCompletedAgents] = useState(new Set());
  const [currentReport, setCurrentReport] = useState('');
  const [finalDecision, setFinalDecision] = useState(null);
  const [runError, setRunError] = useState(null);
  const logEndRef = useRef(null);

  // Fetch initial run data
  useEffect(() => {
    getRun(runId).then(setRun).catch(() => {});
  }, [runId]);

  // Process WebSocket events
  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[events.length - 1];

    if (latest.type === 'agent_start') {
      setActiveAgents(prev => new Set([...prev, latest.agent]));
    }
    if (latest.type === 'agent_complete') {
      setActiveAgents(prev => { const s = new Set(prev); s.delete(latest.agent); return s; });
      setCompletedAgents(prev => new Set([...prev, latest.agent]));
      if (latest.report_content) setCurrentReport(latest.report_content);
    }
    if (latest.type === 'run_complete') {
      setFinalDecision(latest.decision);
    }
    if (latest.type === 'run_error') {
      setRunError(latest.error);
    }
  }, [events]);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const getAgentStatus = (name) => {
    if (completedAgents.has(name)) return 'completed';
    if (activeAgents.has(name)) return 'running';
    return 'pending';
  };

  const logEvents = events.filter(e => e.type !== 'ping');

  return (
    <div className="live-viewer">
      <div className="live-header">
        <div>
          <h1>Live Analysis {run?.ticker && <span className="ticker-badge">{run.ticker}</span>}</h1>
          <p className="text-muted text-sm">
            {run?.trade_date} · 
            <span className={`ws-status ${connected ? 'connected' : 'disconnected'}`}>
              {connected ? ' ● Connected' : ' ○ Disconnected'}
            </span>
          </p>
        </div>
        {finalDecision && (
          <Link to={`/runs/${runId}`} className="btn btn-primary btn-sm">View Full Report →</Link>
        )}
      </div>

      <div className="live-grid">
        {/* Agent Pipeline */}
        <div className="pipeline-panel glass-card">
          <h3>Agent Pipeline</h3>
          <div className="agent-list">
            {AGENT_PIPELINE.map((agent) => {
              const status = getAgentStatus(agent.name);
              return (
                <div key={agent.name} className={`agent-row ${status}`}>
                  <span className="agent-icon">{agent.icon}</span>
                  <div className="agent-info">
                    <span className="agent-name">{agent.name}</span>
                    <span className="agent-phase text-xs text-muted">{agent.phase}</span>
                  </div>
                  <span className={`agent-status-dot ${status}`}>
                    {status === 'completed' && '✓'}
                    {status === 'running' && <span className="dot-pulse" />}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Main Content */}
        <div className="live-main">
          {/* Final Decision Banner */}
          {finalDecision && (
            <div className="decision-banner glass-card animate-fade-in">
              <div className="decision-label">Final Decision</div>
              <div className="decision-text">{finalDecision}</div>
            </div>
          )}

          {runError && (
            <div className="error-banner glass-card">
              <div className="decision-label" style={{ color: 'var(--accent-red)' }}>Error</div>
              <div className="text-sm">{runError}</div>
            </div>
          )}

          {/* Current Report */}
          {currentReport && (
            <div className="report-panel glass-card">
              <h3>Latest Report</h3>
              <div className="report-content">
                <ReactMarkdown>{currentReport}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Log Stream */}
          <div className="log-panel glass-card">
            <h3>Live Log Stream</h3>
            <div className="log-stream">
              {logEvents.length === 0 ? (
                <div className="log-empty text-muted">Waiting for events...</div>
              ) : (
                logEvents.map((ev, i) => (
                  <div key={i} className={`log-entry ${ev.type}`}>
                    <span className="log-time font-mono text-xs">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                    <span className={`log-type ${ev.type}`}>{ev.type}</span>
                    <span className="log-msg">
                      {ev.type === 'agent_start' && `${ev.agent} started`}
                      {ev.type === 'agent_complete' && `${ev.agent} completed`}
                      {ev.type === 'tool_call' && `${ev.agent} → ${ev.tool}`}
                      {ev.type === 'log' && ev.message}
                      {ev.type === 'run_complete' && `Analysis complete: ${ev.decision}`}
                      {ev.type === 'run_error' && `Error: ${ev.error}`}
                    </span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
