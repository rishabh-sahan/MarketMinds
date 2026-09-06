import { useState } from 'react';
import { classNames as cx } from '../lib/format';
import Icon from '../components/ui/Icon';

/**
 * Transient confirmations.
 *
 * Returns a `push` function and the `view` element to render — toasts are
 * per-page rather than global, because every surface that raises one already
 * renders its own container.
 */
export function useToast() {
  const [toasts, setToasts] = useState([]);

  const push = (message, tone = 'accent') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  };

  const view = (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cx(
            'animate-fade-up pointer-events-auto flex items-center gap-2 rounded-lg border px-3.5 py-2.5',
            'text-[13px] font-medium shadow-md',
            t.tone === 'danger'
              ? 'border-danger-border bg-danger-soft text-danger'
              : 'border-line bg-surface text-ink',
          )}
        >
          <Icon name={t.tone === 'danger' ? 'alert' : 'check'} size={14} />
          {t.message}
        </div>
      ))}
    </div>
  );

  return { push, view };
}
