import { Link } from 'react-router-dom';
import './Landing.css';

const FEATURES = [
  {
    icon: '📊',
    title: 'Market Analysis',
    desc: 'Technical indicators, MACD, RSI, Bollinger Bands — analyzed by an AI Market Analyst in real time.',
    color: 'cyan',
  },
  {
    icon: '💬',
    title: 'Sentiment Intelligence',
    desc: 'Aggregates StockTwits, Reddit, and news headlines into a unified sentiment read.',
    color: 'purple',
  },
  {
    icon: '📰',
    title: 'News & Macro',
    desc: 'Monitors global events — Fed rates, GDP, geopolitics — and interprets their market impact.',
    color: 'cyan',
  },
  {
    icon: '📈',
    title: 'Fundamentals Deep Dive',
    desc: 'Balance sheets, cash flow, income statements — the financial health of any company.',
    color: 'purple',
  },
  {
    icon: '⚔️',
    title: 'Bull vs Bear Debate',
    desc: 'Two AI researchers argue for and against the stock, judged by a Research Manager.',
    color: 'cyan',
  },
  {
    icon: '🛡️',
    title: 'Risk Management',
    desc: 'Aggressive, conservative, and neutral risk analysts debate to stress-test every decision.',
    color: 'purple',
  },
];

const PIPELINE_STEPS = [
  { num: 'I', title: 'Analyst Team', agents: '4 Analysts', desc: 'Market, Sentiment, News, Fundamentals' },
  { num: 'II', title: 'Research Team', agents: '3 Researchers', desc: 'Bull/Bear Debate + Manager' },
  { num: 'III', title: 'Trader', agents: '1 Trader', desc: 'Concrete Transaction Proposal' },
  { num: 'IV', title: 'Risk Team', agents: '3 Analysts', desc: 'Aggressive/Conservative/Neutral' },
  { num: 'V', title: 'Portfolio Manager', agents: 'Final Decision', desc: 'Buy / Hold / Sell' },
];

export default function Landing() {
  return (
    <div className="landing">
      {/* Hero */}
      <section className="hero">
        <div className="hero-bg-glow" />
        <div className="hero-content animate-fade-in">
          <div className="hero-badge">
            <span className="badge-dot" />
            Open Source · v0.2.5
          </div>
          <h1 className="hero-title">
            Multi-Agent AI<br />
            <span className="text-gradient">Trading Framework</span>
          </h1>
          <p className="hero-subtitle">
            12 specialized LLM agents collaborate like a real trading firm — analysts, researchers,
            traders, and risk managers — to deliver actionable Buy / Hold / Sell decisions.
          </p>
          <div className="hero-actions">
            <Link to="/dashboard" className="btn btn-primary btn-lg">
              Launch Dashboard →
            </Link>
            <Link to="/runs/new" className="btn btn-secondary btn-lg">
              Start Analysis
            </Link>
          </div>
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="stat-value">12</span>
              <span className="stat-label">AI Agents</span>
            </div>
            <div className="stat-divider" />
            <div className="hero-stat">
              <span className="stat-value">14+</span>
              <span className="stat-label">LLM Providers</span>
            </div>
            <div className="stat-divider" />
            <div className="hero-stat">
              <span className="stat-value">5</span>
              <span className="stat-label">Analysis Phases</span>
            </div>
          </div>
        </div>
      </section>

      {/* Pipeline */}
      <section className="pipeline-section">
        <h2 className="section-title">How It <span className="text-gradient">Works</span></h2>
        <p className="section-subtitle text-muted">Five phases, twelve agents, one decision.</p>
        <div className="pipeline">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={i} className="pipeline-step glass-card">
              <div className="step-num">{step.num}</div>
              <h3>{step.title}</h3>
              <span className="step-agents">{step.agents}</span>
              <p className="text-muted text-sm">{step.desc}</p>
              {i < PIPELINE_STEPS.length - 1 && <div className="step-arrow">→</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="features-section">
        <h2 className="section-title">Powered by <span className="text-gradient">Intelligence</span></h2>
        <p className="section-subtitle text-muted">Every angle covered, every risk debated.</p>
        <div className="features-grid stagger-children">
          {FEATURES.map((f, i) => (
            <div key={i} className={`feature-card glass-card`}>
              <div className={`feature-icon ${f.color}`}>{f.icon}</div>
              <h3>{f.title}</h3>
              <p className="text-muted text-sm">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="cta-card glass-card">
          <h2>Ready to Analyze?</h2>
          <p className="text-muted">Pick a ticker, choose your LLM, and let the agents work.</p>
          <Link to="/runs/new" className="btn btn-primary btn-lg">
            Start Your First Run →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <p className="text-muted text-sm">
          Built by <a href="https://github.com/TauricResearch" target="_blank" rel="noreferrer">Tauric Research</a> · 
          Not financial advice · <a href="https://arxiv.org/abs/2412.20138" target="_blank" rel="noreferrer">arXiv Paper</a>
        </p>
      </footer>
    </div>
  );
}
