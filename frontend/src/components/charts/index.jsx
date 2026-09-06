/**
 * Charts.
 *
 * Hand-drawn SVG rather than a charting library: there are only a few shapes
 * to show, they all need to follow the theme through CSS variables, and a
 * dependency would bring its own styling to fight. Every chart degrades to an
 * honest empty state rather than drawing an axis with nothing on it.
 */

import { classNames as cx, compactNumber, formatNumber } from '../../lib/format';
import Icon from '../ui/Icon';

/** Colour roles, resolved through the theme tokens. */
const TONE_FILL = {
  accent: 'fill-accent',
  buy: 'fill-buy',
  sell: 'fill-sell',
  hold: 'fill-hold',
  muted: 'fill-ink-muted',
};

// `currentColor` in the area gradient resolves through these.
const TONE_TEXT = {
  accent: 'text-accent',
  buy: 'text-buy',
  sell: 'text-sell',
  hold: 'text-hold',
  muted: 'text-ink-muted',
};

const TONE_STROKE = {
  accent: 'stroke-accent',
  buy: 'stroke-buy',
  sell: 'stroke-sell',
  hold: 'stroke-hold',
  muted: 'stroke-ink-muted',
};

/* ---------------------------------------------------------- stat tile --- */

export function StatTile({ label, value, sublabel, tone = 'neutral', icon, className = '' }) {
  const valueTone = {
    neutral: 'text-ink',
    accent: 'text-accent-text',
    buy: 'text-buy',
    sell: 'text-sell',
    hold: 'text-hold',
    danger: 'text-danger',
  }[tone];

  return (
    <div
      className={cx(
        'rounded-xl border border-line bg-surface px-4 py-3.5 shadow-sm',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11.5px] font-medium tracking-wide text-ink-muted uppercase">
          {label}
        </span>
        {icon}
      </div>
      <div className={cx('mt-1.5 text-[22px] leading-none font-semibold tabular-nums', valueTone)}>
        {value}
      </div>
      {sublabel && <div className="mt-1.5 text-[12px] text-ink-muted">{sublabel}</div>}
    </div>
  );
}

/* --------------------------------------------------------- rating bar --- */

/**
 * Horizontal distribution of the five-tier rating scale.
 * Ordered bullish → bearish so the shape itself reads directionally.
 */
export function RatingDistribution({ counts = {}, order, className = '' }) {
  const labels = order || ['Buy', 'Overweight', 'Hold', 'Underweight', 'Sell'];
  const rows = labels.map((label) => ({ label, count: counts[label] || 0 }));
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  const max = Math.max(1, ...rows.map((r) => r.count));

  const tone = (label) => {
    if (label === 'Buy' || label === 'Overweight') return 'bg-buy';
    if (label === 'Sell' || label === 'Underweight') return 'bg-sell';
    return 'bg-hold';
  };

  if (!total) {
    return (
      <p className={cx('py-6 text-center text-[13px] text-ink-muted', className)}>
        No completed runs yet.
      </p>
    );
  }

  return (
    <div className={cx('space-y-2.5', className)}>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-3">
          <span className="w-[86px] shrink-0 text-[12.5px] text-ink-secondary">{row.label}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
            <div
              className={cx('h-full rounded-full transition-[width] duration-500', tone(row.label))}
              style={{ width: `${(row.count / max) * 100}%`, opacity: row.count ? 1 : 0 }}
            />
          </div>
          <span className="w-7 shrink-0 text-right text-[12.5px] tabular-nums text-ink-secondary">
            {row.count}
          </span>
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------- sparkline ---- */

/**
 * Activity over time. Draws an area under a smoothed polyline; a single data
 * point renders as a dot rather than a degenerate line.
 */
export function Sparkline({
  data = [],
  height = 56,
  tone = 'accent',
  className = '',
  showAxis = true,
}) {
  if (!data.length) {
    return (
      <p className={cx('py-6 text-center text-[13px] text-ink-muted', className)}>
        Nothing recorded yet.
      </p>
    );
  }

  const width = 300;
  const pad = 3;
  const values = data.map((d) => d.count ?? d.value ?? 0);
  const max = Math.max(1, ...values);
  const stepX = data.length > 1 ? (width - pad * 2) / (data.length - 1) : 0;

  const points = values.map((v, i) => [
    pad + i * stepX,
    height - pad - (v / max) * (height - pad * 2),
  ]);

  const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = `${line} L${points.at(-1)[0].toFixed(1)} ${height - pad} L${points[0][0].toFixed(1)} ${height - pad} Z`;
  const gradientId = `mm-spark-${tone}`;

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`Activity across ${data.length} days, peaking at ${max}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.18" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* No `fill-*` utility here: a CSS fill would beat the gradient
            attribute and flatten the area into a solid block. */}
        {data.length > 1 && (
          <path d={area} className={TONE_TEXT[tone]} fill={`url(#${gradientId})`} />
        )}
        <path
          d={line}
          fill="none"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          className={TONE_STROKE[tone]}
        />
        {points.length === 1 && (
          <circle cx={points[0][0]} cy={points[0][1]} r="3" className={TONE_FILL[tone]} />
        )}
        <circle
          cx={points.at(-1)[0]}
          cy={points.at(-1)[1]}
          r="2.5"
          className={TONE_FILL[tone]}
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      {showAxis && (
        <div className="mt-1.5 flex justify-between text-[11px] text-ink-muted">
          <span>{data[0].date || data[0].label}</span>
          <span>{data.at(-1).date || data.at(-1).label}</span>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- donut --- */

/** Token split, drawn as a two-segment ring with the total in the middle. */
export function TokenDonut({ tokensIn = 0, tokensOut = 0, size = 128, className = '' }) {
  const total = tokensIn + tokensOut;
  const radius = size / 2 - 11;
  const circumference = 2 * Math.PI * radius;
  const inShare = total ? tokensIn / total : 0;

  return (
    <div className={cx('flex items-center gap-5', className)}>
      <svg width={size} height={size} className="shrink-0 -rotate-90" role="img" aria-label="Token split">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="11"
          className="stroke-surface-2"
        />
        {total > 0 && (
          <>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              strokeWidth="11"
              strokeLinecap="round"
              className="stroke-accent transition-[stroke-dasharray] duration-700"
              strokeDasharray={`${circumference * inShare} ${circumference}`}
            />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              strokeWidth="11"
              strokeLinecap="round"
              className="stroke-buy transition-all duration-700"
              strokeDasharray={`${circumference * (1 - inShare)} ${circumference}`}
              strokeDashoffset={-circumference * inShare}
            />
          </>
        )}
      </svg>

      <div className="min-w-0 space-y-2.5">
        <div>
          <div className="text-[11.5px] tracking-wide text-ink-muted uppercase">Total tokens</div>
          <div className="text-[19px] font-semibold tabular-nums text-ink">
            {compactNumber(total)}
          </div>
        </div>
        <LegendRow color="bg-accent" label="Input" value={formatNumber(tokensIn)} />
        <LegendRow color="bg-buy" label="Output" value={formatNumber(tokensOut)} />
      </div>
    </div>
  );
}

function LegendRow({ color, label, value }) {
  return (
    <div className="flex items-center gap-2 text-[12.5px]">
      <span className={cx('h-2 w-2 shrink-0 rounded-full', color)} />
      <span className="text-ink-muted">{label}</span>
      <span className="ml-auto pl-3 tabular-nums text-ink-secondary">{value}</span>
    </div>
  );
}

/* ------------------------------------------------------- ranked bars ---- */

/** Simple ranked list with an inline proportional bar (top tickers, etc.). */
export function RankedBars({ items = [], labelKey = 'ticker', valueKey = 'count', className = '', onSelect }) {
  if (!items.length) {
    return (
      <p className={cx('py-6 text-center text-[13px] text-ink-muted', className)}>
        Nothing to rank yet.
      </p>
    );
  }
  const max = Math.max(1, ...items.map((i) => i[valueKey] || 0));

  return (
    <div className={cx('space-y-1', className)}>
      {items.map((item) => {
        const label = item[labelKey];
        const value = item[valueKey] || 0;
        const Row = onSelect ? 'button' : 'div';
        return (
          <Row
            key={label}
            onClick={onSelect ? () => onSelect(label) : undefined}
            className={cx(
              'relative flex w-full items-center gap-3 overflow-hidden rounded-lg px-2.5 py-1.5 text-left',
              onSelect && 'transition-colors hover:bg-surface-2',
            )}
          >
            <span
              aria-hidden="true"
              className="absolute inset-y-0 left-0 rounded-lg bg-accent-soft"
              style={{ width: `${(value / max) * 100}%` }}
            />
            <span className="relative z-10 truncate font-mono text-[12.5px] font-medium text-ink">
              {label}
            </span>
            <span className="relative z-10 ml-auto shrink-0 text-[12.5px] tabular-nums text-ink-secondary">
              {value}
            </span>
          </Row>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------ progress ring --- */

/** Compact completion ring used on the live pipeline header. */
export function ProgressRing({ value = 0, total = 1, size = 40, label, className = '' }) {
  const ratio = total > 0 ? Math.min(1, value / total) : 0;
  const done = ratio >= 1;
  const radius = size / 2 - 3.5;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className={cx('relative shrink-0', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="3"
          className="stroke-surface-3"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          className="stroke-accent transition-[stroke-dasharray] duration-500"
          strokeDasharray={`${circumference * ratio} ${circumference}`}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10.5px] font-semibold tabular-nums text-ink">
        {/* "100" does not fit the ring legibly, and a tick reads faster anyway. */}
        {label ?? (done ? <Icon name="check" size={14} className="text-buy" /> : `${Math.round(ratio * 100)}%`)}
      </span>
    </div>
  );
}
