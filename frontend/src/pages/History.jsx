import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listRuns } from '../services/api';
import './History.css';

export default function History() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ ticker: '', status: '' });

  const fetchRuns = () => {
    setLoading(true);
    const params = {};
    if (filter.ticker) params.ticker = filter.ticker;
    if (filter.status) params.status = filter.status;
    listRuns(params)
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchRuns(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchRuns();
  };

  const getDecisionColor = (decision) => {
    if (!decision) return '';
    const d = decision.toLowerCase();
    if (d.includes('buy') || d.includes('bullish')) return 'bullish';
    if (d.includes('sell') || d.includes('bearish')) return 'bearish';
    return 'neutral';
  };

  const getDuration = (run) => {
    if (!run.completed_at || !run.created_at) return '—';
    const ms = new Date(run.completed_at) - new Date(run.created_at);
    const mins = Math.floor(ms / 60000);
    const secs = Math.floor((ms % 60000) / 1000);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="history-page">
      <div className="page-header">
        <div>
          <h1>Analysis History</h1>
          <p className="text-muted">Browse and search past trading analysis runs</p>
        </div>
      </div>

      {/* Filters */}
      <form className="filters glass-card" onSubmit={handleSearch}>
        <input
          className="input"
          type="text"
          placeholder="Filter by ticker (e.g. NVDA)"
          value={filter.ticker}
          onChange={(e) => setFilter(f => ({ ...f, ticker: e.target.value.toUpperCase() }))}
        />
        <select
          className="input"
          value={filter.status}
          onChange={(e) => setFilter(f => ({ ...f, status: e.target.value }))}
        >
          <option value="">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="running">Running</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </select>
        <button type="submit" className="btn btn-secondary">Search</button>
      </form>

      {/* Results */}
      <div className="history-results">
        {loading ? (
          <div className="empty-state">
            <div className="spinner" />
            <p className="text-muted">Loading history...</p>
          </div>
        ) : runs.length === 0 ? (
          <div className="empty-state glass-card">
            <div className="empty-icon">📋</div>
            <h3>No runs found</h3>
            <p className="text-muted">
              {filter.ticker || filter.status
                ? 'Try adjusting your filters.'
                : 'Start your first analysis to see results here.'}
            </p>
            <Link to="/runs/new" className="btn btn-primary mt-md">Start Analysis</Link>
          </div>
        ) : (
          <div className="history-list">
            {runs.map((run) => (
              <Link key={run.id} to={run.status === 'running' ? `/runs/${run.id}/live` : `/runs/${run.id}`} className="history-item glass-card">
                <div className="history-item-left">
                  <span className="ticker-badge">{run.ticker}</span>
                  <div className="history-meta">
                    <span className="font-mono text-sm">{run.trade_date}</span>
                    <span className="text-muted text-xs">{new Date(run.created_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="history-item-center">
                  {run.final_decision ? (
                    <span className={`decision-badge ${getDecisionColor(run.final_decision)}`}>
                      {run.final_decision.substring(0, 60)}
                    </span>
                  ) : (
                    <span className="text-muted text-sm">—</span>
                  )}
                </div>
                <div className="history-item-right">
                  <span className={`badge badge-${run.status}`}>{run.status}</span>
                  <span className="text-muted text-xs">{getDuration(run)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
