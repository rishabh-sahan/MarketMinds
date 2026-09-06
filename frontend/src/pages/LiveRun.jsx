import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { cancelRun, getRun } from '../lib/api';
import { classNames as cx, formatDuration, statusTone } from '../lib/format';
import { AGENT_BY_NAME, PIPELINE } from '../lib/pipeline';
import { useRunStream } from '../hooks/useRunStream';
import AgentPipeline from '../components/run/AgentPipeline';
import EventLog from '../components/run/EventLog';
import ReportView, { DecisionCard } from '../components/run/ReportView';
import UsageStats from '../components/run/UsageStats';
import {
  Alert,
  Badge,
  Button,
  Card,
  Icon,
  Modal,
  Spinner,
  StatusDot,
} from '../components/ui';
import { useToast } from '../hooks/useToast';

export default function LiveRun() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [pinnedAgent, setPinnedAgent] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const toast = useToast();

  const stream = useRunStream(runId);
  const { hydrate } = stream;
  const hydratedRef = useRef(false);

  // Seed the stream from REST once, so a page opened mid-run (or reloaded)
  // shows the progress that already happened.
  useEffect(() => {
    let cancelled = false;
    getRun(runId)
      .then((data) => {
        if (cancelled) return;
        setRun(data);
        if (!hydratedRef.current) {
          hydrate(data);
          hydratedRef.current = true;
        }
      })
      .catch((err) => !cancelled && setLoadError(err.message));
    return () => {
      cancelled = true;
    };
  }, [runId, hydrate]);

  const status = stream.status || run?.status;
  const isActive = status === 'running' || status === 'pending';

  // Elapsed time ticks locally rather than waiting on the next event.
  useEffect(() => {
    const startedAt = run?.started_at || run?.created_at;
    if (!startedAt) return undefined;
    const start = new Date(startedAt).getTime();

    const tick = () => {
      const end = stream.isTerminal && run?.completed_at
        ? new Date(run.completed_at).getTime()
        : Date.now();
      setElapsed(Math.max(0, (end - start) / 1000));
    };

    tick();
    if (!isActive) return undefined;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [run?.started_at, run?.created_at, run?.completed_at, isActive, stream.isTerminal]);

  // Re-fetch once the run finishes, to pick up result_json and final timings.
  useEffect(() => {
    if (!stream.isTerminal) return;
    getRun(runId).then(setRun).catch(() => {});
  }, [stream.isTerminal, runId]);

  const selectedAnalysts = run?.config_snapshot?.selected_analysts;

  const runningAgent = useMemo(
    () => PIPELINE.find((a) => stream.agentStatus[a.agent] === 'running')?.agent || null,
    [stream.agentStatus],
  );

  // Show the pinned agent if the reader picked one, otherwise follow the work:
  // whoever is running, else whichever report last changed.
  const focusAgent = useMemo(() => {
    if (pinnedAgent) return pinnedAgent;
    if (runningAgent) return runningAgent;
    if (stream.activeReportKey) {
      const match = PIPELINE.find((a) => a.reportKey === stream.activeReportKey);
      if (match) return match.agent;
    }
    const done = PIPELINE.filter((a) => stream.agentStatus[a.agent] === 'completed');
    return done.at(-1)?.agent || PIPELINE[0].agent;
  }, [pinnedAgent, runningAgent, stream.activeReportKey, stream.agentStatus]);

  const focusEntry = AGENT_BY_NAME[focusAgent];
  const focusContent = focusEntry ? stream.reports[focusEntry.reportKey] : '';

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await cancelRun(runId);
      toast.push('Cancellation requested — stopping after the current step');
      setConfirmCancel(false);
    } catch (err) {
      toast.push(err.message, 'danger');
    } finally {
      setCancelling(false);
    }
  };

  if (loadError) {
    return (
      <Alert title="Run not found" action={<Button as={Link} to="/history" size="sm">History</Button>}>
        {loadError}
      </Alert>
    );
  }

  if (!run) {
    return (
      <div className="flex items-center gap-2.5 py-20 text-[13.5px] text-ink-muted">
        <Spinner size={16} />
        Loading run…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {toast.view}

      {/* ------------------------------------------------------------ header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button as={Link} to="/history" variant="ghost" size="icon" aria-label="Back to history">
            <Icon name="arrowLeft" size={16} />
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h1 className="font-mono text-[20px] leading-tight font-semibold tracking-tight text-ink">
                {run.ticker}
              </h1>
              <Badge tone={statusTone(status)}>
                <StatusDot tone={statusTone(status)} pulse={isActive} />
                {status}
              </Badge>
            </div>
            <p className="mt-0.5 flex items-center gap-2 text-[12.5px] text-ink-muted">
              <span>as of {run.trade_date}</span>
              <span aria-hidden="true">·</span>
              <span className="tabular-nums">{formatDuration(elapsed)}</span>
              {run.config_snapshot?.llm_provider && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="font-mono">{run.config_snapshot.deep_think_llm}</span>
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isActive && (
            <Button variant="danger" size="sm" icon="stop" onClick={() => setConfirmCancel(true)}>
              Stop run
            </Button>
          )}
          {stream.isTerminal && (
            <Button
              as={Link}
              to={`/runs/${runId}`}
              variant="primary"
              size="sm"
              iconRight="arrowRight"
            >
              Full report
            </Button>
          )}
        </div>
      </div>

      {/* --------------------------------------------------------- outcomes */}
      {stream.decision && (
        <DecisionCard decision={stream.decision} ticker={run.ticker} tradeDate={run.trade_date} />
      )}

      {stream.error && (
        <Alert title="Run failed">
          <span className="font-mono text-[12px] break-all">{stream.error}</span>
        </Alert>
      )}

      {status === 'cancelled' && !stream.error && (
        <Alert tone="hold" icon="stop" title="Run cancelled">
          The pipeline stopped early, so no final rating was produced. Reports written before the
          stop are still shown below.
        </Alert>
      )}

      <UsageStats stats={stream.stats} elapsedSeconds={elapsed} />

      {/* ------------------------------------------------------------ panes */}
      <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="h-[520px] overflow-hidden xl:h-[640px]">
          <AgentPipeline
            statuses={stream.agentStatus}
            selectedAnalysts={selectedAnalysts}
            activeAgent={focusAgent}
            onSelect={(agent) => setPinnedAgent(agent.agent)}
          />
        </Card>

        <div className="flex flex-col gap-4">
          <Card className="h-[360px] overflow-hidden xl:h-[400px]">
            <ReportView
              title={focusEntry?.agent}
              agent={focusAgent}
              content={focusContent}
              status={stream.agentStatus[focusAgent]}
              meta={focusEntry?.role}
              actions={
                pinnedAgent && (
                  <button
                    onClick={() => setPinnedAgent(null)}
                    className="flex items-center gap-1 text-[12px] font-medium text-accent-text hover:underline"
                  >
                    <Icon name="activity" size={12} />
                    Follow live
                  </button>
                )
              }
            />
          </Card>

          <Card className={cx('overflow-hidden', 'h-[220px] xl:h-[224px]')}>
            <EventLog events={stream.log} connected={stream.connected} live={isActive} />
          </Card>
        </div>
      </div>

      <Modal
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title="Stop this run?"
        description="The pipeline stops after the agent currently talking to its provider finishes. Reports already written are kept, but no final rating is produced."
        footer={
          <>
            <Button size="sm" onClick={() => setConfirmCancel(false)}>
              Keep running
            </Button>
            <Button variant="danger" size="sm" icon="stop" loading={cancelling} onClick={handleCancel}>
              Stop run
            </Button>
          </>
        }
      />
    </div>
  );
}
