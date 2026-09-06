import { useEffect, useRef, useState } from 'react';
import { classNames as cx, formatTime } from '../../lib/format';
import { Icon } from '../ui';

/**
 * The live event stream.
 *
 * Reads as a trace rather than a console: each row says which agent acted and
 * what it did, with tool calls carrying their arguments. It follows the tail
 * automatically, but stops following the moment the reader scrolls up.
 */

const TYPE_META = {
  agent_start: { label: 'start', tone: 'text-accent-text bg-accent-soft border-accent-border' },
  agent_complete: { label: 'done', tone: 'text-buy bg-buy-soft border-buy-border' },
  tool_call: { label: 'tool', tone: 'text-hold bg-hold-soft border-hold-border' },
  log: { label: 'info', tone: 'text-ink-secondary bg-surface-2 border-line' },
  run_complete: { label: 'final', tone: 'text-buy bg-buy-soft border-buy-border' },
  run_error: { label: 'error', tone: 'text-danger bg-danger-soft border-danger-border' },
  run_cancelled: { label: 'stop', tone: 'text-ink-secondary bg-surface-2 border-line' },
  error: { label: 'error', tone: 'text-danger bg-danger-soft border-danger-border' },
  run_status: { label: 'state', tone: 'text-ink-secondary bg-surface-2 border-line' },
};

function describe(event) {
  switch (event.type) {
    case 'agent_start':
      return `${event.agent} started`;
    case 'agent_complete':
      return `${event.agent} finished`;
    case 'tool_call':
      return `${event.agent || 'Agent'} called ${event.tool}`;
    case 'run_complete':
      return `Analysis complete — final rating ${event.decision}`;
    case 'run_error':
      return event.error || 'Run failed';
    case 'run_cancelled':
      return 'Run cancelled';
    case 'error':
      return event.message || 'Error';
    case 'run_status':
      return `Run is ${event.status}`;
    default:
      return event.message || '';
  }
}

/** Tool arguments, rendered as a compact `key=value` trail. */
function ArgTrail({ args }) {
  const entries = Object.entries(args || {}).filter(([, v]) => v !== '' && v != null);
  if (!entries.length) return null;

  return (
    <span className="ml-1.5 text-ink-muted">
      {entries.slice(0, 4).map(([key, value], i) => (
        <span key={key}>
          {i > 0 && ' '}
          <span className="opacity-70">{key}=</span>
          <span>{String(Array.isArray(value) ? value.join(',') : value).slice(0, 44)}</span>
        </span>
      ))}
      {entries.length > 4 && <span className="opacity-70"> +{entries.length - 4}</span>}
    </span>
  );
}

export default function EventLog({ events = [], connected, live = true, className = '' }) {
  const scrollRef = useRef(null);
  const [following, setFollowing] = useState(true);

  useEffect(() => {
    if (!following) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events, following]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    // Anything within a few pixels of the bottom still counts as following.
    setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < 24);
  };

  return (
    <div className={cx('flex h-full min-h-0 flex-col', className)}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3.5">
        <h2 className="flex items-center gap-2 text-[14px] font-semibold tracking-tight text-ink">
          <Icon name="activity" size={15} className="text-ink-muted" />
          Event stream
        </h2>

        <div className="flex items-center gap-3">
          {!following && (
            <button
              onClick={() => setFollowing(true)}
              className="flex items-center gap-1 text-[12px] font-medium text-accent-text hover:underline"
            >
              <Icon name="chevronDown" size={12} />
              Follow
            </button>
          )}
          {live && (
            <span className="flex items-center gap-1.5 text-[12px] text-ink-muted">
              <span
                className={cx(
                  'h-1.5 w-1.5 rounded-full',
                  connected ? 'animate-pulse-ring bg-buy' : 'bg-ink-muted',
                )}
              />
              {connected ? 'Live' : 'Reconnecting…'}
            </span>
          )}
        </div>
      </div>

      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="min-h-0 flex-1 overflow-y-auto px-2 py-2 font-mono text-[12px] leading-relaxed"
      >
        {events.length === 0 ? (
          <p className="px-3 py-8 text-center font-sans text-[13px] text-ink-muted">
            {live ? 'Waiting for the first agent to report in…' : 'No events recorded.'}
          </p>
        ) : (
          <ul className="space-y-px">
            {events.map((event, i) => {
              const meta = TYPE_META[event.type] || TYPE_META.log;
              return (
                <li
                  key={`${event.timestamp}-${i}`}
                  className="flex items-start gap-2.5 rounded px-2 py-1 hover:bg-surface-2"
                >
                  <span className="shrink-0 pt-px text-ink-muted tabular-nums">
                    {formatTime(event.timestamp)}
                  </span>
                  <span
                    className={cx(
                      'shrink-0 rounded border px-1 text-[10.5px] font-semibold',
                      meta.tone,
                    )}
                  >
                    {meta.label}
                  </span>
                  <span className="min-w-0 flex-1 break-words text-ink-secondary">
                    {describe(event)}
                    {event.type === 'tool_call' && <ArgTrail args={event.args} />}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
