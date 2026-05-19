import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRun } from '../services/api';
import ReactMarkdown from 'react-markdown';
import './RunDetail.css';

export default function RunDetail() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    getRun(runId)
      .then(setRun)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="run-detail">
        <div className="empty-state"><div className="spinner" /><p className="text-muted">Loading run details...</p></div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="run-detail">
        <div className="empty-state glass-card">
          <h3>Run not found</h3>
          <Link to="/history" className="btn btn-primary mt-md">← Back to History</Link>
        </div>
      </div>
    );
  }

  const result = run.result_json || {};

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'analysts', label: 'Analyst Reports' },
    { key: 'research', label: 'Research Debate' },
    { key: 'risk', label: 'Risk Analysis' },
    { key: 'decision', label: 'Final Decision' },
  ];

  const getDuration = () => {
    if (!run.completed_at || !run.created_at) return '—';
    const ms = new Date(run.completed_at) - new Date(run.created_at);
    const mins = Math.floor(ms / 60000);
    const secs = Math.floor((ms % 60000) / 1000);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="run-detail">
      {/* Header */}
      <div className="detail-header">
        <div>
          <div className="flex items-center gap-md">
            <Link to="/history" className="btn btn-ghost btn-sm">← Back</Link>
            <h1>
              <span className="ticker-badge">{run.ticker}</span>
              Analysis Report
            </h1>
          </div>
          <div className="detail-meta text-sm text-muted">
            {run.trade_date} · {getDuration()} · <span className={`badge badge-${run.status}`}>{run.status}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="detail-tabs">
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="detail-content animate-fade-in" key={activeTab}>
        {activeTab === 'overview' && (
          <div className="overview-grid">
            <div className="overview-card glass-card">
              <h3>Configuration</h3>
              <div className="config-summary">
                {run.config_snapshot && Object.entries(run.config_snapshot).map(([k, v]) => (
                  <div key={k} className="config-row">
                    <span className="font-mono text-xs">{k}</span>
                    <span className="text-sm">{Array.isArray(v) ? v.join(', ') : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
            {run.final_decision && (
              <div className="overview-card glass-card decision-overview">
                <h3>Final Decision</h3>
                <div className="decision-text-lg">{run.final_decision}</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'analysts' && (
          <div className="reports-stack">
            {result.market_report && (
              <div className="report-section glass-card">
                <h3>📊 Market Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.market_report}</ReactMarkdown></div>
              </div>
            )}
            {result.sentiment_report && (
              <div className="report-section glass-card">
                <h3>💬 Sentiment Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.sentiment_report}</ReactMarkdown></div>
              </div>
            )}
            {result.news_report && (
              <div className="report-section glass-card">
                <h3>📰 News Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.news_report}</ReactMarkdown></div>
              </div>
            )}
            {result.fundamentals_report && (
              <div className="report-section glass-card">
                <h3>📈 Fundamentals Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.fundamentals_report}</ReactMarkdown></div>
              </div>
            )}
            {!result.market_report && !result.sentiment_report && !result.news_report && !result.fundamentals_report && (
              <div className="empty-state"><p className="text-muted">No analyst reports available.</p></div>
            )}
          </div>
        )}

        {activeTab === 'research' && (
          <div className="reports-stack">
            {result.investment_debate?.bull_history && (
              <div className="report-section glass-card">
                <h3>🐂 Bull Researcher</h3>
                <div className="report-body"><ReactMarkdown>{result.investment_debate.bull_history}</ReactMarkdown></div>
              </div>
            )}
            {result.investment_debate?.bear_history && (
              <div className="report-section glass-card">
                <h3>🐻 Bear Researcher</h3>
                <div className="report-body"><ReactMarkdown>{result.investment_debate.bear_history}</ReactMarkdown></div>
              </div>
            )}
            {result.investment_debate?.judge_decision && (
              <div className="report-section glass-card">
                <h3>🧠 Research Manager</h3>
                <div className="report-body"><ReactMarkdown>{result.investment_debate.judge_decision}</ReactMarkdown></div>
              </div>
            )}
            {result.investment_plan && (
              <div className="report-section glass-card">
                <h3>📋 Investment Plan</h3>
                <div className="report-body"><ReactMarkdown>{result.investment_plan}</ReactMarkdown></div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'risk' && (
          <div className="reports-stack">
            {result.risk_debate?.aggressive_history && (
              <div className="report-section glass-card">
                <h3>🔥 Aggressive Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.risk_debate.aggressive_history}</ReactMarkdown></div>
              </div>
            )}
            {result.risk_debate?.conservative_history && (
              <div className="report-section glass-card">
                <h3>🛡️ Conservative Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.risk_debate.conservative_history}</ReactMarkdown></div>
              </div>
            )}
            {result.risk_debate?.neutral_history && (
              <div className="report-section glass-card">
                <h3>⚖️ Neutral Analyst</h3>
                <div className="report-body"><ReactMarkdown>{result.risk_debate.neutral_history}</ReactMarkdown></div>
              </div>
            )}
            {result.trader_investment_plan && (
              <div className="report-section glass-card">
                <h3>💰 Trader Proposal</h3>
                <div className="report-body"><ReactMarkdown>{result.trader_investment_plan}</ReactMarkdown></div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'decision' && (
          <div className="reports-stack">
            {result.final_trade_decision ? (
              <div className="report-section glass-card decision-section">
                <h3>👔 Portfolio Manager — Final Decision</h3>
                <div className="report-body"><ReactMarkdown>{result.final_trade_decision}</ReactMarkdown></div>
              </div>
            ) : (
              <div className="empty-state"><p className="text-muted">No final decision available.</p></div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
