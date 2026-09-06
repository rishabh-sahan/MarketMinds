import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { classNames as cx } from '../lib/format';
import { ANALYSTS, PHASES, PHASE_BLURBS, PIPELINE } from '../lib/pipeline';
import { Logo, ThemeToggle } from '../components/layout/AppShell';
import { Button, Icon } from '../components/ui';

export default function Landing() {
  const navigate = useNavigate();
  const [ticker, setTicker] = useState('');

  const start = (e) => {
    e.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    // Carry the typed symbol through so the run form opens pre-filled.
    navigate(symbol ? `/runs/new?ticker=${encodeURIComponent(symbol)}` : '/runs/new');
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* ------------------------------------------------------------- nav */}
      <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <Logo />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button as={Link} to="/dashboard" variant="primary" size="sm" iconRight="arrowRight">
              Open the desk
            </Button>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------ hero */}
      <section className="mx-auto max-w-6xl px-5 pt-16 pb-14 sm:pt-24 sm:pb-20">
        <div className="mx-auto max-w-2xl text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-border bg-accent-soft px-3 py-1 text-[12px] font-medium text-accent-text">
            <Icon name="spark" size={12} />
            Twelve agents, one call on Indian equities
          </span>

          <h1 className="mt-5 text-[38px] leading-[1.08] font-semibold tracking-[-0.03em] text-ink sm:text-[52px]">
            A research desk that
            <br />
            <span className="text-accent">argues with itself.</span>
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-ink-secondary sm:text-[16px]">
            Built for the NSE and BSE. Four analysts gather evidence with their own tools — price
            action against the Nifty, RBI and SEBI policy, Indian media coverage, and the exchange
            filings. A bull and a bear fight over it, a trader turns the verdict into a proposal,
            and a risk committee tears into that before a portfolio manager issues the final rating
            in rupees.
          </p>

          <form onSubmit={start} className="mx-auto mt-8 flex max-w-md gap-2">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Enter an NSE ticker — RELIANCE"
              aria-label="Ticker symbol"
              className={cx(
                'h-11 flex-1 rounded-xl border border-line bg-surface px-4 font-mono text-[14px]',
                'text-ink shadow-sm placeholder:font-sans placeholder:text-ink-muted',
                'transition-colors hover:border-line-strong focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none',
              )}
            />
            <Button type="submit" variant="primary" size="lg" iconRight="arrowRight">
              Analyse
            </Button>
          </form>

          <p className="mt-3 text-[12px] text-ink-muted">
            Research and educational use only. Not financial advice.
          </p>
        </div>
      </section>

      {/* -------------------------------------------------------- pipeline */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-5 py-14 sm:py-16">
          <div className="mb-9 max-w-xl">
            <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-ink">
              How a rating gets made
            </h2>
            <p className="mt-2 text-[14px] leading-relaxed text-ink-secondary">
              A LangGraph state machine. Each analyst loops with its own tools until it can write a
              report; the reports feed a structured debate, and the debate feeds the decision.
            </p>
          </div>

          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {PHASES.map((phase, i) => {
              const agents = PIPELINE.filter((a) => a.phase === phase);
              return (
                <li
                  key={phase}
                  className="relative rounded-xl border border-line bg-bg p-4 transition-shadow hover:shadow-md"
                >
                  <span className="font-mono text-[11px] text-ink-muted">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <h3 className="mt-1 text-[14px] font-semibold text-ink">{phase}</h3>
                  <p className="mt-1 text-[12.5px] leading-snug text-ink-muted">
                    {PHASE_BLURBS[phase]}
                  </p>

                  <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                    {agents.map((agent) => (
                      <li key={agent.agent} className="flex items-center gap-2">
                        <Icon name={agent.icon} size={13} className="shrink-0 text-accent" />
                        <span className="truncate text-[12px] text-ink-secondary">
                          {agent.agent}
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* --------------------------------------------------------- analysts */}
      <section className="mx-auto max-w-6xl px-5 py-14 sm:py-16">
        <div className="mb-8 max-w-xl">
          <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-ink">
            The analyst team
          </h2>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-secondary">
            Pick any combination. Each one reads different evidence, and the debate downstream is
            only as good as what they bring to it.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {ANALYSTS.map((analyst) => (
            <div
              key={analyst.key}
              className="flex items-start gap-3.5 rounded-xl border border-line bg-surface p-5 shadow-sm"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-accent-border bg-accent-soft text-accent">
                <Icon name={analyst.icon} size={17} />
              </span>
              <div className="min-w-0">
                <h3 className="text-[14px] font-semibold text-ink">{analyst.agent}</h3>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-secondary">
                  {analyst.blurb}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------------------------------------------- features */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto max-w-6xl px-5 py-14 sm:py-16">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: 'activity',
                title: 'Watch it think',
                body: 'Every agent transition and tool call streams over a WebSocket, with reports appearing the moment they are written.',
              },
              {
                icon: 'memory',
                title: 'It remembers',
                body: 'Each call is logged, then resolved against real prices and benchmark alpha on the next run — and the reflection feeds the next decision.',
              },
              {
                icon: 'cpu',
                title: 'Fourteen providers',
                body: 'OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, MiniMax, Sarvam, OpenRouter, or a local Ollama runtime.',
              },
              {
                icon: 'scale',
                title: 'Tunable depth',
                body: 'Set how many rounds the bull and bear trade, and how long the risk committee argues, per run.',
              },
              {
                icon: 'news',
                title: 'Full audit trail',
                body: 'Every analyst report, both sides of each debate, and the timeline of the run — exportable as one markdown document.',
              },
              {
                icon: 'layers',
                title: 'Indian sources, no keys',
                body: 'Google News India, Economic Times, Moneycontrol, Mint, Business Standard and Hindu BusinessLine, plus NSE corporate filings — all free.',
              },
              {
                icon: 'target',
                title: 'Five-tier ratings',
                body: 'Buy, Overweight, Hold, Underweight or Sell, with a thesis, an executive summary, and a rupee price target.',
              },
            ].map((feature) => (
              <div key={feature.title} className="rounded-xl border border-line bg-bg p-5">
                <Icon name={feature.icon} size={18} className="text-accent" />
                <h3 className="mt-3 text-[14px] font-semibold text-ink">{feature.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-secondary">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- cta */}
      <section className="mx-auto max-w-6xl px-5 py-16 sm:py-20">
        <div className="rounded-2xl border border-line bg-surface px-6 py-12 text-center shadow-sm sm:px-12">
          <h2 className="text-[26px] font-semibold tracking-[-0.02em] text-ink">
            Put a ticker in front of the desk
          </h2>
          <p className="mx-auto mt-2.5 max-w-md text-[14px] leading-relaxed text-ink-secondary">
            A full run takes a few minutes. You will see every argument that produced the rating.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2.5">
            <Button as={Link} to="/runs/new" variant="primary" size="lg" icon="play">
              Start an analysis
            </Button>
            <Button as={Link} to="/dashboard" size="lg" iconRight="arrowRight">
              View the dashboard
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-5 py-6 text-[12.5px] text-ink-muted sm:flex-row">
          <Logo size="sm" />
          <p>Research and educational use only. Output is not financial advice.</p>
        </div>
      </footer>
    </div>
  );
}
