import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { cancelRun, deleteRun, downloadRunReport, listRuns } from '../lib/api';
import {
  durationBetween,
  formatDuration,
  ratingTone,
  relativeTime,
  RUN_STATUSES,
  statusTone,
} from '../lib/format';
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Select,
  StatusDot,
} from '../components/ui';
import { useToast } from '../hooks/useToast';

const PAGE_SIZE = 25;

export default function History() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busyId, setBusyId] = useState(null);

  // Filters live in the URL so a filtered view can be linked and reloaded. The
  // ticker box is uncontrolled and keyed on that value, so it resets whenever
  // the URL changes without needing a state mirror.
  const ticker = params.get('ticker') || '';
  const status = params.get('status') || '';

  const fetchRuns = useCallback(
    () =>
      listRuns({ ticker, status, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
        .then((data) => {
          setRuns(data);
          setError(null);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false)),
    [ticker, status, page],
  );

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const load = () => {
    setLoading(true);
    fetchRuns();
  };

  const setFilter = (patch) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setPage(0);
    setParams(next);
  };

  const handleCancel = async (run) => {
    setBusyId(run.id);
    try {
      await cancelRun(run.id);
      toast.push(`Stopping ${run.ticker}`);
      load();
    } catch (err) {
      toast.push(err.message, 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    setBusyId(pendingDelete.id);
    try {
      await deleteRun(pendingDelete.id);
      toast.push('Run deleted');
      setPendingDelete(null);
      load();
    } catch (err) {
      toast.push(err.message, 'danger');
    } finally {
      setBusyId(null);
    }
  };

  const handleExport = async (run) => {
    try {
      await downloadRunReport(run.id, `marketminds-${run.ticker}-${run.trade_date}.md`);
    } catch (err) {
      toast.push(err.message, 'danger');
    }
  };

  const hasFilters = Boolean(ticker || status);

  return (
    <div className="space-y-5">
      {toast.view}

      <PageHeader title="History" description="Every analysis this desk has run.">
        <Button size="sm" icon="refresh" onClick={load} loading={loading}>
          Refresh
        </Button>
        <Button as={Link} to="/runs/new" variant="primary" size="sm" icon="plus">
          New analysis
        </Button>
      </PageHeader>

      {/* ---------------------------------------------------------- filters */}
      <Card className="p-3">
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const value = new FormData(e.currentTarget).get('ticker') || '';
            setFilter({ ticker: String(value).trim().toUpperCase() });
          }}
        >
          <div className="relative min-w-[180px] flex-1">
            <Icon
              name="search"
              size={14}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted"
            />
            <Input
              key={ticker}
              name="ticker"
              defaultValue={ticker}
              placeholder="Filter by ticker"
              className="pl-8.5 font-mono uppercase"
              aria-label="Filter by ticker"
            />
          </div>

          <Select
            value={status}
            onChange={(e) => setFilter({ status: e.target.value })}
            className="w-[150px]"
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            {RUN_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>

          <Button type="submit" size="md" icon="search">
            Search
          </Button>

          {hasFilters && (
            <Button
              type="button"
              variant="ghost"
              size="md"
              icon="x"
              onClick={() => {
                setParams(new URLSearchParams());
                setPage(0);
              }}
            >
              Clear
            </Button>
          )}
        </form>
      </Card>

      {error && (
        <Alert title="Could not load runs" action={<Button size="sm" onClick={load}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {/* ------------------------------------------------------------ table */}
      <Card className="overflow-hidden">
        {loading && runs.length === 0 ? (
          <LoadingRows rows={6} />
        ) : runs.length === 0 ? (
          <EmptyState
            icon="history"
            title={hasFilters ? 'No runs match those filters' : 'No runs yet'}
            description={
              hasFilters
                ? 'Try a different ticker or status.'
                : 'Start an analysis and it will appear here with its full report.'
            }
            action={
              hasFilters ? (
                <Button size="sm" onClick={() => setParams(new URLSearchParams())}>
                  Clear filters
                </Button>
              ) : (
                <Button as={Link} to="/runs/new" variant="primary" size="sm" icon="plus">
                  New analysis
                </Button>
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse">
              <thead>
                <tr className="border-b border-line text-left">
                  {['Ticker', 'As of', 'Status', 'Rating', 'Duration', 'Started', ''].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2.5 text-[11.5px] font-semibold tracking-wide text-ink-muted uppercase"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {runs.map((run) => {
                  const active = run.status === 'running' || run.status === 'pending';
                  const href = active ? `/runs/${run.id}/live` : `/runs/${run.id}`;
                  return (
                    <tr
                      key={run.id}
                      onClick={() => navigate(href)}
                      className="cursor-pointer transition-colors hover:bg-surface-2"
                    >
                      <td className="px-4 py-2.5 font-mono text-[13px] font-semibold text-ink">
                        {run.ticker}
                      </td>
                      <td className="px-4 py-2.5 text-[12.5px] text-ink-secondary">
                        {run.trade_date}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge tone={statusTone(run.status)}>
                          <StatusDot tone={statusTone(run.status)} pulse={run.status === 'running'} />
                          {run.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        {run.final_decision ? (
                          <Badge tone={ratingTone(run.final_decision)}>{run.final_decision}</Badge>
                        ) : (
                          <span className="text-[12.5px] text-ink-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-[12.5px] tabular-nums text-ink-secondary">
                        {formatDuration(durationBetween(run.created_at, run.completed_at))}
                      </td>
                      <td className="px-4 py-2.5 text-[12.5px] text-ink-muted">
                        {relativeTime(run.created_at)}
                      </td>
                      <td
                        className="px-4 py-2.5 text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex justify-end gap-1">
                          {active ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Stop ${run.ticker}`}
                              title="Stop run"
                              loading={busyId === run.id}
                              onClick={() => handleCancel(run)}
                            >
                              <Icon name="stop" size={14} />
                            </Button>
                          ) : (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`Export ${run.ticker}`}
                                title="Export markdown"
                                onClick={() => handleExport(run)}
                              >
                                <Icon name="download" size={14} />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`Delete ${run.ticker}`}
                                title="Delete run"
                                onClick={() => setPendingDelete(run)}
                                className="hover:text-danger"
                              >
                                <Icon name="trash" size={14} />
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* --------------------------------------------------------- paginate */}
      {(page > 0 || runs.length === PAGE_SIZE) && (
        <div className="flex items-center justify-between">
          <p className="text-[12.5px] text-ink-muted">
            Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + runs.length}
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              icon="arrowLeft"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              iconRight="arrowRight"
              disabled={runs.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={`Delete ${pendingDelete?.ticker} run?`}
        description="The run, its reports and its event history are removed permanently."
        footer={
          <>
            <Button size="sm" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon="trash"
              loading={busyId === pendingDelete?.id}
              onClick={handleDelete}
            >
              Delete run
            </Button>
          </>
        }
      />
    </div>
  );
}
