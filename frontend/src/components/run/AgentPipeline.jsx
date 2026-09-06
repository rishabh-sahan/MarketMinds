import { classNames as cx } from '../../lib/format';
import { PHASES, PHASE_BLURBS, PIPELINE } from '../../lib/pipeline';
import { ProgressRing } from '../charts';
import { Icon, Spinner } from '../ui';

/**
 * The agent pipeline.
 *
 * Status comes straight from the backend's own inference over the graph state,
 * so a running agent here is genuinely mid-call — the shimmer is a fact about
 * the run, not decoration.
 */
export default function AgentPipeline({
  statuses = {},
  selectedAnalysts,
  activeAgent,
  onSelect,
  selectedKey,
  compact = false,
}) {
  // Only show analysts that were actually chosen for this run.
  const agents = PIPELINE.filter(
    (a) => !a.analystKey || !selectedAnalysts || selectedAnalysts.includes(a.analystKey),
  );

  const completed = agents.filter((a) => statuses[a.agent] === 'completed').length;
  const running = agents.filter((a) => statuses[a.agent] === 'running');

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
        <ProgressRing value={completed} total={agents.length} size={38} />
        <div className="min-w-0 flex-1">
          <h2 className="text-[14px] font-semibold tracking-tight text-ink">Agent pipeline</h2>
          <p className="truncate text-[12.5px] text-ink-muted">
            {running.length
              ? `${running[0].agent} is working…`
              : `${completed} of ${agents.length} agents complete`}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {PHASES.map((phase) => {
          const phaseAgents = agents.filter((a) => a.phase === phase);
          if (!phaseAgents.length) return null;

          const phaseDone = phaseAgents.every((a) => statuses[a.agent] === 'completed');
          const phaseActive = phaseAgents.some((a) => statuses[a.agent] === 'running');

          return (
            <section key={phase} className="mb-3 last:mb-0">
              <div className="flex items-center gap-2 px-2 pb-1.5">
                <h3
                  className={cx(
                    'text-[10.5px] font-semibold tracking-[0.07em] uppercase transition-colors',
                    phaseActive ? 'text-accent' : phaseDone ? 'text-ink-secondary' : 'text-ink-muted',
                  )}
                >
                  {phase}
                </h3>
                <span className="h-px flex-1 bg-line" />
                {phaseDone && <Icon name="check" size={11} className="text-buy" />}
              </div>

              {!compact && (
                <p className="px-2 pb-1.5 text-[11.5px] leading-snug text-ink-muted">
                  {PHASE_BLURBS[phase]}
                </p>
              )}

              <ul className="space-y-0.5">
                {phaseAgents.map((agent) => (
                  <AgentRow
                    key={agent.agent}
                    agent={agent}
                    status={statuses[agent.agent] || 'pending'}
                    active={activeAgent === agent.agent || selectedKey === agent.reportKey}
                    onSelect={onSelect}
                    compact={compact}
                  />
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function AgentRow({ agent, status, active, onSelect, compact }) {
  const clickable = Boolean(onSelect);
  const Row = clickable ? 'button' : 'div';

  return (
    <li>
      <Row
        onClick={clickable ? () => onSelect(agent) : undefined}
        aria-current={active ? 'true' : undefined}
        className={cx(
          'flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors',
          clickable && 'hover:bg-surface-2',
          active && 'bg-accent-soft',
        )}
      >
        <span
          className={cx(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition-colors',
            status === 'completed'
              ? 'border-buy-border bg-buy-soft text-buy'
              : status === 'running'
                ? 'animate-pulse-ring border-accent-border bg-accent-soft text-accent'
                : 'border-line bg-surface-2 text-ink-muted',
          )}
        >
          <Icon name={agent.icon} size={14} />
        </span>

        <span className="min-w-0 flex-1">
          <span
            className={cx(
              'block truncate text-[12.5px] font-medium',
              status === 'pending' ? 'text-ink-muted' : 'text-ink',
            )}
          >
            {agent.agent}
          </span>
          {!compact && (
            <span
              className={cx(
                'block truncate text-[11.5px]',
                status === 'running' ? 'text-accent-text' : 'text-ink-muted',
              )}
            >
              {status === 'running' ? 'Thinking…' : agent.role}
            </span>
          )}
        </span>

        <span className="flex w-4 shrink-0 justify-center">
          {status === 'completed' && <Icon name="check" size={13} className="text-buy" />}
          {status === 'running' && <Spinner size={13} className="text-accent" />}
        </span>
      </Row>
    </li>
  );
}
