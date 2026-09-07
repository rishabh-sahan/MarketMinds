import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { deleteRun, downloadRunReport, getRun } from '../lib/api';
import {
  classNames as cx,
  durationBetween,
  formatDateTime,
  formatDuration,
  statusTone,
} from '../lib/format';
import { AGENT_BY_NAME, REPORT_SECTIONS, readSection } from '../lib/pipeline';
import ReportView, { DecisionCard } from '../components/run/ReportView';
import EventLog from '../components/run/EventLog';
import UsageStats from '../components/run/UsageStats';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  MetaItem,
  Modal,
  Spinner,
  StatusDot,
  Tabs,
} from '../components/ui';
import { useToast } from '../hooks/useToast';

const GROUPS = ['Analysis', 'Debate', 'Risk', 'Decision'];

export default function RunDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('report');
  // Null means "no explicit choice yet", which resolves to the first section
  // that exists — deriving this avoids a render pass just to pick a default.
  const [selected, setSelected] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();

  useEffect(() => {
    getRun(runId)
      .then(setRun)
      .catch((err) => setError(err.message));
  }, [runId]);

  // Only sections the run actually produced are worth showing.
  const sections = useMemo(() => {
    if (!run?.result_json) return [];
    return REPORT_SECTIONS.filter((s) => readSection(run.result_json, s).trim());
  }, [run]);

  const events = useMemo(
    () =>
      (run?.events || []).map((e) => ({
        type: e.event_type,
        agent: e.agent_name,
        tool: e.payload?.tool,
        args: e.payload?.args,
        message: e.payload?.error || e.payload?.message,
        decision: e.payload?.decision,
        error: e.payload?.error,
        timestamp: e.timestamp,
      })),
    [run],
  );

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteRun(runId);
      navigate('/history');
    } catch (err) {
      toast.push(err.message, 'danger');
      setDeleting(false);
    }
  };

  const handleExport = async () => {
    try {
      await downloadRunReport(runId, `marketminds-${run.ticker}-${run.trade_date}.pdf`);
      toast.push('PDF downloaded');
    } catch (err) {
      toast.push(err.message, 'danger');
    }
  };

  if (error) {
    return (
      <Alert title="Run not found" action={<Button as={Link} to="/history" size="sm">History</Button>}>
        {error}
      </Alert>
    );
  }

  if (!run) {
    return (
      <div className="flex items-center gap-2.5 py-20 text-[13.5px] text-ink-muted">
        <Spinner size={16} />
        Loading report…
      </div>
    );
  }

  const cfg = run.config_snapshot || {};
  const duration = durationBetween(run.started_at || run.created_at, run.completed_at);
  const active = run.status === 'running' || run.status === 'pending';
  const activeKey = selected ?? sections[0]?.key;
  const activeSection = sections.find((s) => s.key === activeKey);

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
              <Badge tone={statusTone(run.status)}>
                <StatusDot tone={statusTone(run.status)} pulse={active} />
                {run.status}
              </Badge>
            </div>
            <p className="mt-0.5 text-[12.5px] text-ink-muted">
              Analysed as of {run.trade_date} · finished {formatDateTime(run.completed_at)}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {active && (
            <Button as={Link} to={`/runs/${runId}/live`} variant="primary" size="sm" icon="activity">
              Watch live
            </Button>
          )}
          {run.result_json && (
            <Button size="sm" icon="download" onClick={handleExport}>
              Export PDF
            </Button>
          )}
          <Button
            variant="danger"
            size="icon"
            aria-label="Delete run"
            onClick={() => setConfirmDelete(true)}
          >
            <Icon name="trash" size={15} />
          </Button>
        </div>
      </div>

      {run.final_decision && (
        <DecisionCard
          decision={run.final_decision}
          ticker={run.ticker}
          tradeDate={run.trade_date}
        />
      )}

      {run.error_message && (
        <Alert title={run.status === 'cancelled' ? 'Run cancelled' : 'Run failed'} tone={run.status === 'cancelled' ? 'hold' : 'danger'}>
          <span className="font-mono text-[12px] break-all">{run.error_message}</span>
        </Alert>
      )}

      {/* -------------------------------------------------------- run facts */}
      <Card>
        <div className="grid grid-cols-2 gap-4 px-5 py-4 sm:grid-cols-3 lg:grid-cols-6">
          <MetaItem label="Provider" value={cfg.llm_provider} />
          <MetaItem label="Deep model" value={cfg.deep_think_llm} mono />
          <MetaItem label="Quick model" value={cfg.quick_think_llm} mono />
          <MetaItem label="Debate rounds" value={`${cfg.max_debate_rounds ?? '—'} / ${cfg.max_risk_discuss_rounds ?? '—'}`} />
          <MetaItem label="Language" value={cfg.output_language} />
          <MetaItem label="Duration" value={formatDuration(duration)} />
        </div>
      </Card>

      {(run.llm_calls || run.tokens_in || run.tool_calls) > 0 && (
        <UsageStats stats={run} elapsedSeconds={duration} />
      )}

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'report', label: 'Reports', icon: 'news', count: sections.length },
          { value: 'timeline', label: 'Timeline', icon: 'activity', count: events.length },
          { value: 'config', label: 'Configuration', icon: 'settings' },
        ]}
      />

      {tab === 'report' &&
        (sections.length === 0 ? (
          <Card>
            <EmptyState
              icon="news"
              title="No reports were produced"
              description={
                active
                  ? 'This run is still in progress — watch it live to see reports as they are written.'
                  : 'The run ended before any agent finished writing.'
              }
              action={
                active && (
                  <Button as={Link} to={`/runs/${runId}/live`} variant="primary" size="sm">
                    Watch live
                  </Button>
                )
              }
            />
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
            <Card className="h-fit overflow-hidden">
              <nav className="p-2">
                {GROUPS.map((group) => {
                  const groupSections = sections.filter((s) => s.group === group);
                  if (!groupSections.length) return null;
                  return (
                    <div key={group} className="mb-2 last:mb-0">
                      <p className="px-2.5 py-1 text-[10.5px] font-semibold tracking-[0.07em] text-ink-muted uppercase">
                        {group}
                      </p>
                      {groupSections.map((section) => {
                        const entry = AGENT_BY_NAME[section.title];
                        const isActive = section.key === activeKey;
                        return (
                          <button
                            key={section.key}
                            onClick={() => setSelected(section.key)}
                            className={cx(
                              'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left transition-colors',
                              isActive
                                ? 'bg-accent-soft text-accent-text'
                                : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
                            )}
                          >
                            <Icon
                              name={entry?.icon || 'news'}
                              size={14}
                              className={isActive ? 'text-accent' : 'text-ink-muted'}
                            />
                            <span className="truncate text-[12.5px] font-medium">
                              {section.title}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </nav>
            </Card>

            <Card className="overflow-hidden">
              {activeSection && (
                <ReportView
                  title={activeSection.title}
                  agent={activeSection.title}
                  meta={AGENT_BY_NAME[activeSection.title]?.role}
                  content={readSection(run.result_json, activeSection)}
                  status="completed"
                  className="max-h-[70vh]"
                />
              )}
            </Card>
          </div>
        ))}

      {tab === 'timeline' && (
        <Card className="h-[560px] overflow-hidden">
          <EventLog events={events} live={false} />
        </Card>
      )}

      {tab === 'config' && (
        <Card>
          <CardHeader
            title="Run configuration"
            icon="settings"
            description="The exact settings this run executed with"
          />
          <div className="divide-y divide-line">
            {Object.entries(cfg).map(([key, value]) => (
              <div key={key} className="flex items-start gap-4 px-5 py-2.5">
                <span className="w-56 shrink-0 font-mono text-[12.5px] text-ink-secondary">
                  {key}
                </span>
                <span className="min-w-0 flex-1 font-mono text-[12.5px] break-words text-ink">
                  {value == null || value === ''
                    ? '—'
                    : typeof value === 'object'
                      ? JSON.stringify(value)
                      : String(value)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete this run?"
        description="The run, its reports and its event history are removed permanently. Entries already written to the decision log are not affected."
        footer={
          <>
            <Button size="sm" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" icon="trash" loading={deleting} onClick={handleDelete}>
              Delete run
            </Button>
          </>
        }
      />
    </div>
  );
}
