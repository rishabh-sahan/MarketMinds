import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getRunStats, listRuns } from '../lib/api';
import SignedOutNotice from '../components/SignedOutNotice';
import {
  compactNumber,
  durationBetween,
  formatDuration,
  ratingTone,
  relativeTime,
  statusTone,
} from '../lib/format';
import { RankedBars, RatingDistribution, Sparkline, StatTile, TokenDonut } from '../components/charts';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  LoadingRows,
  PageHeader,
  StatusDot,
} from '../components/ui';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  // `loading` starts true, so the first fetch never has to set it — that keeps
  // the mount effect free of synchronous state updates.
  const fetchAll = useCallback(
    () =>
      Promise.all([getRunStats(), listRuns({ limit: 8 })])
        .then(([s, r]) => {
          setStats(s);
          setRuns(r);
          setError(null);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const load = () => {
    setLoading(true);
    fetchAll();
  };

  // A run in flight will change on its own, so refresh while one is active.
  const hasActive = runs.some((r) => r.status === 'running' || r.status === 'pending');
  useEffect(() => {
    if (!hasActive) return undefined;
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [hasActive, fetchAll]);

  if (loading && !stats) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" description="Loading your research history…" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <LoadingRows rows={1} />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const totalTokens = (stats?.tokens_in || 0) + (stats?.tokens_out || 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="What the agent desk has produced so far."
      >
        <Button size="sm" icon="refresh" onClick={load} loading={loading}>
          Refresh
        </Button>
        <Button as={Link} to="/runs/new" variant="primary" size="sm" icon="plus">
          New analysis
        </Button>
      </PageHeader>

      <SignedOutNotice what="analyses" />

      {error && (
        <Alert title="Could not reach the API" action={<Button size="sm" onClick={load}>Retry</Button>}>
          {error}. Check that the backend is running on port 8000.
        </Alert>
      )}

      {/* Headline counters */}
      <div className="stagger grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total runs"
          value={stats?.total ?? 0}
          sublabel={`${stats?.completed ?? 0} completed`}
          icon={<Icon name="layers" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="In flight"
          value={stats?.running ?? 0}
          tone={stats?.running ? 'accent' : 'neutral'}
          sublabel={stats?.pending ? `${stats.pending} queued or orphaned` : 'Nothing running'}
          icon={<Icon name="activity" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="Avg duration"
          value={stats?.avg_duration_seconds ? formatDuration(stats.avg_duration_seconds) : '—'}
          sublabel="Across completed runs"
          icon={<Icon name="clock" size={15} className="text-ink-muted" />}
        />
        <StatTile
          label="Tokens used"
          value={compactNumber(totalTokens)}
          tone={totalTokens ? 'neutral' : 'neutral'}
          sublabel={`${compactNumber(stats?.llm_calls ?? 0)} LLM calls`}
          icon={<Icon name="cpu" size={15} className="text-ink-muted" />}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Recent runs */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent runs"
            icon="history"
            description="The eight most recent analyses"
            action={
              <Button as={Link} to="/history" variant="ghost" size="sm" iconRight="arrowRight">
                All runs
              </Button>
            }
          />
          {runs.length === 0 ? (
            <EmptyState
              icon="spark"
              title="No analyses yet"
              description="Pick a ticker and a date, choose your analyst team, and the desk goes to work."
              action={
                <Button as={Link} to="/runs/new" variant="primary" size="sm" icon="plus">
                  Run your first analysis
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-line">
              {runs.map((run) => (
                <li key={run.id}>
                  <button
                    onClick={() =>
                      navigate(
                        run.status === 'running' || run.status === 'pending'
                          ? `/runs/${run.id}/live`
                          : `/runs/${run.id}`,
                      )
                    }
                    className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-surface-2"
                  >
                    <StatusDot
                      tone={statusTone(run.status)}
                      pulse={run.status === 'running'}
                    />
                    <span className="w-24 shrink-0 truncate font-mono text-[13px] font-semibold text-ink">
                      {run.ticker}
                    </span>
                    <span className="hidden w-24 shrink-0 text-[12.5px] text-ink-muted sm:block">
                      {run.trade_date}
                    </span>
                    <span className="min-w-0 flex-1">
                      {run.final_decision ? (
                        <Badge tone={ratingTone(run.final_decision)}>{run.final_decision}</Badge>
                      ) : (
                        <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                      )}
                    </span>
                    <span className="hidden shrink-0 text-[12px] text-ink-muted md:block">
                      {formatDuration(durationBetween(run.created_at, run.completed_at))}
                    </span>
                    <span className="w-24 shrink-0 text-right text-[12px] text-ink-muted">
                      {relativeTime(run.created_at)}
                    </span>
                    <Icon name="chevronRight" size={14} className="shrink-0 text-ink-muted" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Rating mix */}
        <Card>
          <CardHeader
            title="Rating mix"
            icon="target"
            description="Across every completed run"
          />
          <div className="px-5 py-4">
            <RatingDistribution counts={stats?.rating_counts} />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Activity" icon="activity" description="Runs started per day" />
          <div className="px-5 py-4">
            <Sparkline data={stats?.runs_per_day || []} height={64} />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Most analysed"
            icon="chart"
            description="Tickers by run count"
          />
          <div className="px-3 py-3">
            <RankedBars
              items={stats?.top_tickers || []}
              onSelect={(ticker) => navigate(`/history?ticker=${encodeURIComponent(ticker)}`)}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Token usage" icon="cpu" description="Input vs output, all runs" />
          <div className="px-5 py-4">
            {totalTokens ? (
              <TokenDonut tokensIn={stats.tokens_in} tokensOut={stats.tokens_out} />
            ) : (
              <p className="py-6 text-center text-[13px] text-ink-muted">
                Token counts are recorded from your next run onward.
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
