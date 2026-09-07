/**
 * Display helpers — dates, durations, counts, and the rating vocabulary.
 */

/** The backend's five-tier scale, ordered most bullish to most bearish. */
export const RATINGS = ['Buy', 'Overweight', 'Hold', 'Underweight', 'Sell'];

/**
 * Map a rating to its semantic tone. Green and red are reserved for these
 * five values alone, so a colour in the UI always means a direction.
 */
export function ratingTone(rating) {
  if (!rating) return 'neutral';
  const r = String(rating).toLowerCase();
  if (r.includes('overweight')) return 'buy-soft';
  if (r.includes('underweight')) return 'sell-soft';
  if (r.includes('buy')) return 'buy';
  if (r.includes('sell')) return 'sell';
  if (r.includes('hold')) return 'hold';
  return 'neutral';
}

export const RUN_STATUSES = ['pending', 'running', 'completed', 'failed', 'cancelled'];

export function statusTone(status) {
  switch (status) {
    case 'completed':
      return 'buy';
    case 'running':
      return 'accent';
    case 'failed':
      return 'danger';
    case 'cancelled':
      return 'neutral';
    default:
      return 'hold';
  }
}

export function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTime(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/** "3 minutes ago", "just now", "2 days ago". */
export function relativeTime(value) {
  if (!value) return '—';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return '—';
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 45) return 'just now';

  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, secs] of units) {
    const value = Math.floor(seconds / secs);
    if (value >= 1) return `${value} ${unit}${value > 1 ? 's' : ''} ago`;
  }
  return 'just now';
}

/** Seconds → "4m 12s" / "42s" / "1h 03m". */
export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins < 60) return `${mins}m ${String(secs).padStart(2, '0')}s`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${String(mins % 60).padStart(2, '0')}m`;
}

/** Elapsed time between two timestamps, either of which may be missing. */
export function durationBetween(start, end) {
  if (!start || !end) return null;
  const ms = new Date(end) - new Date(start);
  if (Number.isNaN(ms) || ms < 0) return null;
  return ms / 1000;
}

/** 1_234_567 → "1.23M"; keeps token counts readable in tight stat tiles. */
export function compactNumber(value) {
  if (value == null || Number.isNaN(value)) return '—';
  const n = Number(value);
  if (Math.abs(n) < 1000) return String(n);
  if (Math.abs(n) < 1e6) return `${(n / 1e3).toFixed(n < 1e4 ? 1 : 0)}K`;
  if (Math.abs(n) < 1e9) return `${(n / 1e6).toFixed(2)}M`;
  return `${(n / 1e9).toFixed(2)}B`;
}

export function formatNumber(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return Number(value).toLocaleString();
}

/** A fraction (0.032) → "+3.2%". */
export function formatPercent(fraction, digits = 1) {
  if (fraction == null || Number.isNaN(fraction)) return '—';
  const pct = fraction * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(digits)}%`;
}

/** Today in YYYY-MM-DD, in the viewer's own timezone. */
export function todayISO() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now - offset).toISOString().split('T')[0];
}

/** Two-letter monogram for a ticker badge. */
export function tickerInitials(ticker) {
  if (!ticker) return '??';
  return String(ticker).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase();
}

export function classNames(...values) {
  return values.filter(Boolean).join(' ');
}
