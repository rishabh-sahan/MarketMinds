import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { classNames as cx, ratingTone } from '../../lib/format';
import { AGENT_BY_NAME } from '../../lib/pipeline';
import { Badge, EmptyState, Icon } from '../ui';

/**
 * Markdown body shared by every report surface.
 *
 * GFM is enabled because the analysts routinely emit pipe tables for indicator
 * readouts and financials; without it those collapse into a run of pipes.
 */
export function Markdown({ children, className = '' }) {
  if (!children) return null;
  return (
    <div className={cx('mm-prose', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

/**
 * One agent's report.
 *
 * While the owning agent is still running the body is shown with a live caret,
 * because these reports arrive in full as each agent finishes rather than
 * token by token — the caret marks "still being written", not a typing effect.
 */
export default function ReportView({
  title,
  agent,
  content,
  status,
  meta,
  actions,
  className = '',
}) {
  const entry = agent ? AGENT_BY_NAME[agent] : null;
  const pending = !content;

  return (
    <article className={cx('flex min-h-0 flex-col', className)}>
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-3.5">
        <div className="flex min-w-0 items-center gap-2.5">
          {entry && (
            <span
              className={cx(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border',
                status === 'running'
                  ? 'border-accent-border bg-accent-soft text-accent'
                  : 'border-line bg-surface-2 text-ink-muted',
              )}
            >
              <Icon name={entry.icon} size={14} />
            </span>
          )}
          <div className="min-w-0">
            <h2 className="truncate text-[14px] font-semibold tracking-tight text-ink">
              {title || agent}
            </h2>
            {meta && <p className="truncate text-[12px] text-ink-muted">{meta}</p>}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {status === 'running' && (
            <Badge tone="accent">
              <span className="animate-pulse-ring h-1.5 w-1.5 rounded-full bg-accent" />
              Writing
            </Badge>
          )}
          {actions}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {pending ? (
          status === 'running' ? (
            <WritingPlaceholder />
          ) : (
            <EmptyState
              icon="clock"
              title="Not written yet"
              description="This agent has not produced its report. It runs later in the pipeline."
            />
          )
        ) : (
          <>
            <Markdown>{content}</Markdown>
            {status === 'running' && (
              <span className="animate-caret ml-0.5 inline-block h-4 w-[7px] translate-y-0.5 bg-accent" />
            )}
          </>
        )}
      </div>
    </article>
  );
}

/** Shimmering skeleton lines shown while an agent is mid-call. */
function WritingPlaceholder() {
  const widths = ['92%', '85%', '96%', '60%', '88%', '73%'];
  return (
    <div className="space-y-2.5" aria-label="Agent is writing its report">
      {widths.map((w, i) => (
        <div key={i} className="shimmer h-3 rounded" style={{ width: w }} />
      ))}
    </div>
  );
}

/**
 * The headline result — the Portfolio Manager's five-tier rating.
 * Given its own visual weight because it is the one thing the whole pipeline
 * exists to produce.
 */
export function DecisionCard({ decision, ticker, tradeDate, className = '', children }) {
  const tone = ratingTone(decision);
  const border = {
    buy: 'border-buy-border bg-buy-soft',
    'buy-soft': 'border-buy-border bg-buy-soft',
    sell: 'border-sell-border bg-sell-soft',
    'sell-soft': 'border-sell-border bg-sell-soft',
    hold: 'border-hold-border bg-hold-soft',
    neutral: 'border-line bg-surface-2',
  }[tone];

  const text = {
    buy: 'text-buy',
    'buy-soft': 'text-buy',
    sell: 'text-sell',
    'sell-soft': 'text-sell',
    hold: 'text-hold',
    neutral: 'text-ink',
  }[tone];

  return (
    <div className={cx('animate-fade-up rounded-xl border px-5 py-4', border, className)}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[11.5px] font-medium tracking-wide text-ink-muted uppercase">
            Final position rating
          </p>
          <p className={cx('mt-1 text-[30px] leading-none font-semibold tracking-tight', text)}>
            {decision || '—'}
          </p>
        </div>

        {(ticker || tradeDate) && (
          <div className="text-right">
            <p className="font-mono text-[18px] font-semibold text-ink">{ticker}</p>
            <p className="text-[12.5px] text-ink-muted">as of {tradeDate}</p>
          </div>
        )}
      </div>
      {children && <div className="mt-3 border-t border-current/10 pt-3">{children}</div>}
    </div>
  );
}
