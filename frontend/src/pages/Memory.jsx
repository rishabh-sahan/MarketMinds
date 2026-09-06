import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMemory } from '../lib/api';
import { classNames as cx, formatPercent, ratingTone } from '../lib/format';
import { Markdown } from '../components/run/ReportView';
import { StatTile } from '../components/charts';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  Input,
  LoadingRows,
  PageHeader,
} from '../components/ui';

/**
 * The decision log.
 *
 * Every completed run appends its call here. On the next run for the same
 * ticker the realised return is fetched, compared against a regional
 * benchmark, and reflected on — and that history is fed back into the
 * Portfolio Manager's prompt. This page is that loop, made visible.
 */
export default function Memory() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [ticker, setTicker] = useState('');
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState(null);

  const fetchMemory = useCallback(
    () =>
      getMemory({ ticker: query || undefined })
        .then((d) => {
          setData(d);
          setError(null);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false)),
    [query],
  );

  useEffect(() => {
    fetchMemory();
  }, [fetchMemory]);

  const load = () => {
    setLoading(true);
    fetchMemory();
  };

  const entries = data?.entries || [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Memory"
        description="Past calls, what they actually returned, and the lessons carried into the next run."
      >
        <Button size="sm" icon="refresh" onClick={load} loading={loading}>
          Refresh
        </Button>
      </PageHeader>

      {error && (
        <Alert title="Could not read the decision log" action={<Button size="sm" onClick={load}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {/* --------------------------------------------------------- headline */}
      <div className="stagger grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Decisions logged"
          value={data?.total ?? 0}
          sublabel={`${data?.resolved ?? 0} resolved · ${data?.pending ?? 0} awaiting prices`}
          icon={<Icon name="memory" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="Mean raw return"
          value={data?.avg_raw_return != null ? formatPercent(data.avg_raw_return) : '—'}
          tone={data?.avg_raw_return > 0 ? 'buy' : data?.avg_raw_return < 0 ? 'sell' : 'neutral'}
          sublabel="Across resolved decisions"
          icon={<Icon name="trendUp" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="Mean alpha"
          value={data?.avg_alpha != null ? formatPercent(data.avg_alpha) : '—'}
          tone={data?.avg_alpha > 0 ? 'buy' : data?.avg_alpha < 0 ? 'sell' : 'neutral'}
          sublabel="Versus the regional benchmark"
          icon={<Icon name="target" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="Fed back into prompts"
          value={data?.resolved ?? 0}
          sublabel="Reflections the PM can read"
          icon={<Icon name="spark" size={15} className="text-ink-muted" />}
        />
      </div>

      {/* --------------------------------------------------------- how it works */}
      <Card className="border-accent-border bg-accent-soft">
        <div className="flex items-start gap-3 px-5 py-3.5">
          <Icon name="info" size={16} className="mt-0.5 shrink-0 text-accent" />
          <p className="text-[12.5px] leading-relaxed text-ink-secondary">
            A decision lands here the moment a run completes, marked{' '}
            <span className="font-medium text-ink">pending</span>. The next time you analyse the
            same ticker, the realised return is fetched, alpha is computed against that market's
            index, a reflection is written, and the entry becomes{' '}
            <span className="font-medium text-ink">resolved</span> — then feeds the Portfolio
            Manager's prompt on every later run.
          </p>
        </div>
      </Card>

      {/* ----------------------------------------------------------- filter */}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(ticker.trim().toUpperCase());
        }}
      >
        <div className="relative max-w-xs flex-1">
          <Icon
            name="search"
            size={14}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted"
          />
          <Input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="Filter by ticker"
            className="pl-8.5 font-mono"
            aria-label="Filter by ticker"
          />
        </div>
        <Button type="submit" icon="search">
          Search
        </Button>
        {query && (
          <Button
            type="button"
            variant="ghost"
            icon="x"
            onClick={() => {
              setTicker('');
              setQuery('');
            }}
          >
            Clear
          </Button>
        )}
      </form>

      {/* ---------------------------------------------------------- entries */}
      <Card className="overflow-hidden">
        <CardHeader
          title="Decision log"
          icon="memory"
          description={data?.path ? <span className="font-mono text-[11.5px]">{data.path}</span> : null}
        />

        {loading && !data ? (
          <LoadingRows rows={5} />
        ) : entries.length === 0 ? (
          <EmptyState
            icon="memory"
            title={query ? `No decisions logged for ${query}` : 'Nothing logged yet'}
            description="Complete an analysis and its call is recorded here, then resolved against real prices on your next run for the same ticker."
            action={
              <Button as={Link} to="/runs/new" variant="primary" size="sm" icon="plus">
                Run an analysis
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-line">
            {entries.map((entry, i) => {
              const id = `${entry.ticker}-${entry.date}-${i}`;
              const open = expanded === id;
              const resolved = entry.status === 'resolved';

              return (
                <li key={id}>
                  <button
                    onClick={() => setExpanded(open ? null : id)}
                    className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-surface-2"
                    aria-expanded={open}
                  >
                    <span className="w-28 shrink-0 truncate font-mono text-[13px] font-semibold text-ink">
                      {entry.ticker}
                    </span>
                    <span className="w-24 shrink-0 text-[12.5px] text-ink-muted">{entry.date}</span>

                    <span className="w-24 shrink-0">
                      <Badge tone={ratingTone(entry.rating)}>{entry.rating || '—'}</Badge>
                    </span>

                    <span className="hidden flex-1 items-center gap-4 sm:flex">
                      <ReturnCell label="Return" value={entry.raw_return} />
                      <ReturnCell label="Alpha" value={entry.alpha_return} />
                      {entry.holding_days != null && (
                        <span className="text-[12px] text-ink-muted">
                          {entry.holding_days}d hold
                        </span>
                      )}
                    </span>

                    <Badge tone={resolved ? 'buy' : 'hold'}>
                      {resolved ? 'resolved' : 'pending'}
                    </Badge>

                    <Icon
                      name="chevronDown"
                      size={14}
                      className={cx(
                        'shrink-0 text-ink-muted transition-transform',
                        open && 'rotate-180',
                      )}
                    />
                  </button>

                  {open && (
                    <div className="animate-fade space-y-4 border-t border-line bg-surface-2 px-5 py-4">
                      {entry.reflection && (
                        <section>
                          <h3 className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold tracking-wide text-ink-muted uppercase">
                            <Icon name="spark" size={12} />
                            Reflection
                          </h3>
                          <div className="rounded-lg border border-accent-border bg-accent-soft px-3.5 py-3">
                            <Markdown>{entry.reflection}</Markdown>
                          </div>
                        </section>
                      )}

                      {entry.decision && (
                        <section>
                          <h3 className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold tracking-wide text-ink-muted uppercase">
                            <Icon name="verdict" size={12} />
                            Decision as written
                          </h3>
                          <div className="rounded-lg border border-line bg-surface px-3.5 py-3">
                            <Markdown>{entry.decision}</Markdown>
                          </div>
                        </section>
                      )}

                      {!entry.reflection && !entry.decision && (
                        <p className="text-[13px] text-ink-muted">
                          No detail was stored for this entry.
                        </p>
                      )}

                      <div className="flex gap-2">
                        <Button
                          as={Link}
                          to={`/history?ticker=${encodeURIComponent(entry.ticker)}`}
                          size="sm"
                          icon="history"
                        >
                          Runs for {entry.ticker}
                        </Button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

function ReturnCell({ label, value }) {
  const tone =
    value == null ? 'text-ink-muted' : value > 0 ? 'text-buy' : value < 0 ? 'text-sell' : 'text-ink';
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-[11.5px] text-ink-muted">{label}</span>
      <span className={cx('text-[12.5px] font-medium tabular-nums', tone)}>
        {value == null ? '—' : formatPercent(value)}
      </span>
    </span>
  );
}
