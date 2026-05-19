import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listProviders, getProviderModels, createRun } from '../services/api';
import './RunConsole.css';

const ANALYSTS = [
  { key: 'market', label: 'Market Analyst', icon: '📊', desc: 'Technical indicators & price trends' },
  { key: 'social', label: 'Sentiment Analyst', icon: '💬', desc: 'StockTwits, Reddit, news sentiment' },
  { key: 'news', label: 'News Analyst', icon: '📰', desc: 'Macro news & global events' },
  { key: 'fundamentals', label: 'Fundamentals Analyst', icon: '📈', desc: 'Balance sheet, cash flow, financials' },
];

export default function RunConsole() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState({ quick: [], deep: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [form, setForm] = useState({
    ticker: '',
    trade_date: new Date().toISOString().split('T')[0],
    llm_provider: 'openai',
    quick_think_llm: 'gpt-5.4-mini',
    deep_think_llm: 'gpt-5.4',
    selected_analysts: ['market', 'social', 'news', 'fundamentals'],
    max_debate_rounds: 1,
    max_risk_discuss_rounds: 1,
    output_language: 'English',
  });

  useEffect(() => {
    listProviders().then(setProviders).catch(() => {});
  }, []);

  useEffect(() => {
    if (form.llm_provider) {
      getProviderModels(form.llm_provider)
        .then((data) => {
          setModels(data);
          if (data.quick.length > 0) setForm(f => ({ ...f, quick_think_llm: data.quick[0].value }));
          if (data.deep.length > 0) setForm(f => ({ ...f, deep_think_llm: data.deep[0].value }));
        })
        .catch(() => setModels({ quick: [], deep: [] }));
    }
  }, [form.llm_provider]);

  const toggleAnalyst = (key) => {
    setForm(f => ({
      ...f,
      selected_analysts: f.selected_analysts.includes(key)
        ? f.selected_analysts.filter(a => a !== key)
        : [...f.selected_analysts, key],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.ticker.trim()) { setError('Please enter a ticker symbol'); return; }
    if (form.selected_analysts.length === 0) { setError('Select at least one analyst'); return; }

    setLoading(true);
    setError(null);
    try {
      const run = await createRun(form);
      navigate(`/runs/${run.id}/live`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="run-console">
      <div className="page-header">
        <div>
          <h1>New Analysis Run</h1>
          <p className="text-muted">Configure and start a new trading analysis</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="run-form">
        {error && <div className="form-error">{error}</div>}

        {/* Row 1: Ticker + Date */}
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Ticker Symbol</label>
            <input
              className="input"
              type="text"
              placeholder="e.g. NVDA, AAPL, 7203.T"
              value={form.ticker}
              onChange={(e) => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Analysis Date</label>
            <input
              className="input"
              type="date"
              value={form.trade_date}
              onChange={(e) => setForm(f => ({ ...f, trade_date: e.target.value }))}
            />
          </div>
        </div>

        {/* Row 2: Provider + Models */}
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">LLM Provider</label>
            <select
              className="input"
              value={form.llm_provider}
              onChange={(e) => setForm(f => ({ ...f, llm_provider: e.target.value }))}
            >
              {providers.map(p => (
                <option key={p.name} value={p.name}>{p.display_name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Quick Thinking Model</label>
            <select
              className="input"
              value={form.quick_think_llm}
              onChange={(e) => setForm(f => ({ ...f, quick_think_llm: e.target.value }))}
            >
              {models.quick.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Deep Thinking Model</label>
            <select
              className="input"
              value={form.deep_think_llm}
              onChange={(e) => setForm(f => ({ ...f, deep_think_llm: e.target.value }))}
            >
              {models.deep.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Analysts Selection */}
        <div className="form-group">
          <label className="form-label">Analyst Team</label>
          <div className="analysts-grid">
            {ANALYSTS.map(a => (
              <button
                key={a.key}
                type="button"
                className={`analyst-card glass-card ${form.selected_analysts.includes(a.key) ? 'selected' : ''}`}
                onClick={() => toggleAnalyst(a.key)}
              >
                <div className="analyst-icon">{a.icon}</div>
                <div>
                  <div className="analyst-name">{a.label}</div>
                  <div className="analyst-desc text-muted text-xs">{a.desc}</div>
                </div>
                <div className={`analyst-check ${form.selected_analysts.includes(a.key) ? 'checked' : ''}`}>
                  {form.selected_analysts.includes(a.key) ? '✓' : ''}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Row 3: Debate rounds + Language */}
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Debate Rounds (Bull/Bear)</label>
            <input
              className="input"
              type="number"
              min="1" max="5"
              value={form.max_debate_rounds}
              onChange={(e) => setForm(f => ({ ...f, max_debate_rounds: parseInt(e.target.value) || 1 }))}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Risk Debate Rounds</label>
            <input
              className="input"
              type="number"
              min="1" max="5"
              value={form.max_risk_discuss_rounds}
              onChange={(e) => setForm(f => ({ ...f, max_risk_discuss_rounds: parseInt(e.target.value) || 1 }))}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Output Language</label>
            <select
              className="input"
              value={form.output_language}
              onChange={(e) => setForm(f => ({ ...f, output_language: e.target.value }))}
            >
              <option value="English">English</option>
              <option value="Chinese">中文</option>
              <option value="Japanese">日本語</option>
              <option value="Korean">한국어</option>
              <option value="Spanish">Español</option>
              <option value="Hindi">हिन्दी</option>
            </select>
          </div>
        </div>

        {/* Submit */}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Starting...
              </>
            ) : (
              '🚀 Start Analysis'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
