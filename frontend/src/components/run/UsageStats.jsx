import { classNames as cx, compactNumber, formatDuration } from '../../lib/format';
import { Icon } from '../ui';

/**
 * Usage counters for a run — LLM calls, tool calls, and token split.
 *
 * Fed by the same LangChain callback handler the terminal CLI uses, so the web
 * and terminal report identical numbers for the same run.
 */
export default function UsageStats({ stats, elapsedSeconds, className = '', layout = 'row' }) {
  const items = [
    { icon: 'cpu', label: 'LLM calls', value: compactNumber(stats?.llm_calls ?? 0) },
    { icon: 'tool', label: 'Tool calls', value: compactNumber(stats?.tool_calls ?? 0) },
    { icon: 'download', label: 'Tokens in', value: compactNumber(stats?.tokens_in ?? 0) },
    { icon: 'spark', label: 'Tokens out', value: compactNumber(stats?.tokens_out ?? 0) },
  ];

  if (elapsedSeconds != null) {
    items.push({ icon: 'clock', label: 'Elapsed', value: formatDuration(elapsedSeconds) });
  }

  return (
    <dl
      className={cx(
        layout === 'row'
          ? 'grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3 lg:grid-cols-5'
          : 'space-y-px overflow-hidden rounded-xl border border-line bg-line',
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.label} className="bg-surface px-3.5 py-2.5">
          <dt className="flex items-center gap-1.5 text-[11px] tracking-wide text-ink-muted uppercase">
            <Icon name={item.icon} size={11} />
            {item.label}
          </dt>
          <dd className="mt-0.5 text-[16px] font-semibold tabular-nums text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
