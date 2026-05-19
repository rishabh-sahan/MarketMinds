import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listRuns } from '../services/api';
import './Dashboard.css';

export default function Dashboard() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listRuns({ limit: 20 })
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  const stats = {
    total: runs.length,
    completed: runs.filter(r => r.status === 'completed').length,
    running: runs.filter(r => r.status === 'running').length,
    failed: runs.filter(r => r.status === 'failed').length,
  };

  return (
    <div className="dashboard">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="text-muted">Overview of your trading analysis runs</p>
        </div>
        <Link to="/runs/new" className="btn btn-primary">
          + New Analysis
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid stagger-children">
        <div className="stat-card glass-card">
          <div className="stat-card-icon cyan">📊</div>
          <div>
            <div className="stat-card-value">{stats.total}</div>
            <div className="stat-card-label text-muted">Total Runs</div>
          </div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-card-icon green">✅</div>
          <div>
            <div className="stat-card-value">{stats.completed}</div>
            <div className="stat-card-label text-muted">Completed</div>
          </div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-card-icon blue">⚡</div>
          <div>
            <div className="stat-card-value">{stats.running}</div>
            <div className="stat-card-label text-muted">Running</div>
          </div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-card-icon red">❌</div>
          <div>
            <div className="stat-card-value">{stats.failed}</div>
            <div className="stat-card-label text-muted">Failed</div>
          </div>
        </div>
      </div>

      {/* Recent Runs Table */}
      <div className="recent-runs glass-card">
        <div className="section-header">
          <h2>Recent Runs</h2>
          <Link to="/history" className="btn btn-ghost btn-sm">View All →</Link>
        </div>
        {loading ? (
          <div className="empty-state">
            <div className="spinner" />
            <p className="text-muted">Loading runs...</p>
          </div>
        ) : runs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🚀</div>
            <h3>No runs yet</h3>
            <p className="text-muted">Start your first analysis to see results here.</p>
            <Link to="/runs/new" className="btn btn-primary mt-md">Start Analysis</Link>
          </div>
        ) : (
          <table className="runs-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Date</th>
                <th>Status</th>
                <th>Decision</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td><span className="ticker-badge">{run.ticker}</span></td>
                  <td className="font-mono text-sm">{run.trade_date}</td>
                  <td><span className={`badge badge-${run.status}`}>{run.status}</span></td>
                  <td className="text-sm">{run.final_decision ? run.final_decision.substring(0, 40) + '...' : '—'}</td>
                  <td className="text-sm text-muted">{new Date(run.created_at).toLocaleString()}</td>
                  <td>
                    <Link to={run.status === 'running' ? `/runs/${run.id}/live` : `/runs/${run.id}`} className="btn btn-ghost btn-sm">
                      {run.status === 'running' ? 'Watch Live' : 'View'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
