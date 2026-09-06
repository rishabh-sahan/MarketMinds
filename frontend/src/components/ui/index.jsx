/**
 * Base UI primitives.
 *
 * Small, unopinionated building blocks shared by every page — kept in one file
 * because each is a handful of lines and they are almost always imported
 * together. Anything with real behaviour (modals, the pipeline, charts) lives
 * in its own module.
 */

import { useEffect, useRef } from 'react';
import { classNames as cx } from '../../lib/format';
import Icon from './Icon';

export { default as Icon } from './Icon';

/* -------------------------------------------------------------- button --- */

const BUTTON_VARIANTS = {
  primary:
    'bg-accent text-on-accent border-accent hover:bg-accent-hover hover:border-accent-hover shadow-sm',
  secondary:
    'bg-surface text-ink border-line hover:bg-surface-2 hover:border-line-strong shadow-sm',
  ghost: 'bg-transparent text-ink-secondary border-transparent hover:bg-surface-2 hover:text-ink',
  danger:
    'bg-transparent text-danger border-danger-border hover:bg-danger-soft',
};

const BUTTON_SIZES = {
  sm: 'h-8 px-3 text-[13px] gap-1.5 rounded-lg',
  md: 'h-9.5 px-4 text-[13.5px] gap-2 rounded-lg',
  lg: 'h-11 px-5 text-[14.5px] gap-2 rounded-xl',
  icon: 'h-9 w-9 justify-center rounded-lg',
};

export function Button({
  as: Component = 'button',
  variant = 'secondary',
  size = 'md',
  icon,
  iconRight,
  loading = false,
  className = '',
  children,
  disabled,
  ...rest
}) {
  return (
    <Component
      className={cx(
        'inline-flex items-center border font-medium transition-colors duration-150',
        'disabled:pointer-events-none disabled:opacity-45',
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      disabled={Component === 'button' ? disabled || loading : undefined}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner size={14} /> : icon ? <Icon name={icon} size={15} /> : null}
      {children}
      {iconRight && !loading ? <Icon name={iconRight} size={15} /> : null}
    </Component>
  );
}

export function Spinner({ size = 16, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={cx('animate-spin-slow shrink-0', className)}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.4" opacity="0.2" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ---------------------------------------------------------------- card --- */

export function Card({ className = '', children, ...rest }) {
  return (
    <div
      className={cx(
        'rounded-xl border border-line bg-surface shadow-sm',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, description, action, icon, className = '' }) {
  return (
    <div
      className={cx(
        'flex items-start justify-between gap-4 border-b border-line px-5 py-3.5',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-[14px] font-semibold tracking-tight text-ink">
          {icon && <Icon name={icon} size={15} className="text-ink-muted" />}
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-[12.5px] text-ink-muted">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* --------------------------------------------------------------- badge --- */

const BADGE_TONES = {
  neutral: 'bg-surface-2 text-ink-secondary border-line',
  accent: 'bg-accent-soft text-accent-text border-accent-border',
  buy: 'bg-buy-soft text-buy border-buy-border',
  'buy-soft': 'bg-buy-soft text-buy border-buy-border',
  sell: 'bg-sell-soft text-sell border-sell-border',
  'sell-soft': 'bg-sell-soft text-sell border-sell-border',
  hold: 'bg-hold-soft text-hold border-hold-border',
  danger: 'bg-danger-soft text-danger border-danger-border',
};

export function Badge({ tone = 'neutral', className = '', icon, children, ...rest }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5',
        'text-[11.5px] font-medium whitespace-nowrap',
        BADGE_TONES[tone] || BADGE_TONES.neutral,
        className,
      )}
      {...rest}
    >
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
}

/** A small coloured dot, optionally pulsing to signal live activity. */
export function StatusDot({ tone = 'neutral', pulse = false, className = '' }) {
  const colors = {
    neutral: 'bg-ink-muted',
    accent: 'bg-accent',
    buy: 'bg-buy',
    sell: 'bg-sell',
    hold: 'bg-hold',
    danger: 'bg-danger',
  };
  return (
    <span
      className={cx(
        'inline-block h-1.5 w-1.5 shrink-0 rounded-full',
        colors[tone] || colors.neutral,
        pulse && 'animate-pulse-ring',
        className,
      )}
    />
  );
}

/* --------------------------------------------------------------- forms --- */

export function Field({ label, hint, error, htmlFor, children, className = '' }) {
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="text-[12.5px] font-medium tracking-tight text-ink-secondary"
        >
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-[12px] text-danger">{error}</p>
      ) : hint ? (
        <p className="text-[12px] leading-relaxed text-ink-muted">{hint}</p>
      ) : null}
    </div>
  );
}

const CONTROL = cx(
  'w-full rounded-lg border border-line bg-surface px-3 text-[13.5px] text-ink',
  'placeholder:text-ink-muted transition-colors',
  'hover:border-line-strong focus:border-accent focus:outline-none',
  'focus:ring-2 focus:ring-accent/20 disabled:opacity-50',
);

export function Input({ className = '', ...rest }) {
  return <input className={cx(CONTROL, 'h-9.5', className)} {...rest} />;
}

export function Textarea({ className = '', rows = 3, ...rest }) {
  return <textarea rows={rows} className={cx(CONTROL, 'py-2 leading-relaxed', className)} {...rest} />;
}

export function Select({ className = '', children, ...rest }) {
  return (
    <div className="relative">
      <select
        className={cx(
          CONTROL,
          'h-9.5 cursor-pointer appearance-none pr-9',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <Icon
        name="chevronDown"
        size={14}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-ink-muted"
      />
    </div>
  );
}

export function Switch({ checked, onChange, label, hint, disabled, id }) {
  return (
    <label
      htmlFor={id}
      className={cx(
        'flex cursor-pointer items-start gap-3',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          'relative mt-0.5 h-5 w-9 shrink-0 rounded-full border transition-colors',
          checked ? 'border-accent bg-accent' : 'border-line-strong bg-surface-2',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 h-3.5 w-3.5 rounded-full shadow-sm transition-all duration-200',
            checked ? 'left-4.5 bg-on-accent' : 'left-0.5 bg-ink-muted',
          )}
        />
      </button>
      {(label || hint) && (
        <span className="min-w-0">
          {label && <span className="block text-[13px] font-medium text-ink">{label}</span>}
          {hint && <span className="mt-0.5 block text-[12px] text-ink-muted">{hint}</span>}
        </span>
      )}
    </label>
  );
}

/* ----------------------------------------------------------- feedback --- */

const ALERT_TONES = {
  danger: 'border-danger-border bg-danger-soft text-danger',
  accent: 'border-accent-border bg-accent-soft text-accent-text',
  hold: 'border-hold-border bg-hold-soft text-hold',
  buy: 'border-buy-border bg-buy-soft text-buy',
};

export function Alert({ tone = 'danger', icon = 'alert', title, children, action, className = '' }) {
  return (
    <div
      className={cx(
        'flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-[13px]',
        ALERT_TONES[tone] || ALERT_TONES.danger,
        className,
      )}
      role={tone === 'danger' ? 'alert' : undefined}
    >
      <Icon name={icon} size={16} className="mt-px shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cx(title && 'mt-0.5', 'break-words opacity-90')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function EmptyState({ icon = 'layers', title, description, action, className = '' }) {
  return (
    <div className={cx('flex flex-col items-center px-6 py-14 text-center', className)}>
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface-2 text-ink-muted">
        <Icon name={icon} size={20} />
      </div>
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-ink-muted">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className = '' }) {
  return <div className={cx('shimmer rounded-md', className)} />;
}

/** Full-panel loading placeholder, sized to roughly match the real content. */
export function LoadingRows({ rows = 4, className = '' }) {
  return (
    <div className={cx('space-y-2.5 p-5', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9" />
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- tabs --- */

export function Tabs({ tabs, value, onChange, className = '' }) {
  return (
    <div
      role="tablist"
      className={cx(
        'flex gap-0.5 overflow-x-auto rounded-lg border border-line bg-surface-2 p-1',
        className,
      )}
    >
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cx(
              'flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5',
              'text-[13px] font-medium whitespace-nowrap transition-colors',
              active
                ? 'bg-surface text-ink shadow-sm'
                : 'text-ink-muted hover:text-ink-secondary',
            )}
          >
            {tab.icon && <Icon name={tab.icon} size={14} />}
            {tab.label}
            {tab.count != null && (
              <span
                className={cx(
                  'rounded px-1 text-[11px] tabular-nums',
                  active ? 'bg-surface-3 text-ink-secondary' : 'text-ink-muted',
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------- modal --- */

export function Modal({ open, onClose, title, description, children, footer }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    document.addEventListener('keydown', onKey);
    // Focus moves into the dialog so Escape and Tab behave as expected.
    ref.current?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="animate-fade fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4 backdrop-blur-[2px]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="animate-fade-up w-full max-w-md rounded-xl border border-line bg-surface shadow-lg outline-none"
      >
        <div className="px-5 pt-5">
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && (
            <p className="mt-1 text-[13px] leading-relaxed text-ink-secondary">{description}</p>
          )}
        </div>
        {children && <div className="px-5 pt-4">{children}</div>}
        <div className="mt-5 flex justify-end gap-2 border-t border-line px-5 py-3.5">
          {footer ?? (
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- layout --- */

export function PageHeader({ title, description, children, className = '' }) {
  return (
    <div
      className={cx(
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="text-[20px] leading-tight font-semibold tracking-[-0.02em] text-ink">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-[13.5px] text-ink-secondary">{description}</p>
        )}
      </div>
      {children && <div className="flex shrink-0 items-center gap-2">{children}</div>}
    </div>
  );
}

/** Small label/value pair used across detail panels. */
export function MetaItem({ label, value, mono = false, tone }) {
  return (
    <div className="min-w-0">
      <div className="text-[11.5px] tracking-wide text-ink-muted uppercase">{label}</div>
      <div
        className={cx(
          'mt-0.5 truncate text-[13px] font-medium',
          mono && 'font-mono text-[12.5px]',
          tone === 'danger' ? 'text-danger' : 'text-ink',
        )}
        title={typeof value === 'string' ? value : undefined}
      >
        {value ?? '—'}
      </div>
    </div>
  );
}
