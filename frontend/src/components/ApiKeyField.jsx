import { useState } from 'react';
import { classNames as cx } from '../lib/format';
import { clearKey, getKey, maskKey, setKey } from '../lib/apiKeys';
import { Alert, Badge, Button, Icon, Input } from './ui';

/**
 * Entry point for a visitor's own provider key.
 *
 * The key is held in this browser only and attached to the run request that
 * needs it — the server never stores it. That is stated plainly in the UI,
 * because asking someone for a credential without saying where it goes is not
 * a reasonable thing to do.
 *
 * The parent remounts this with `key={provider}` when the provider changes, so
 * the initial state below is always read fresh for the right provider and no
 * synchronising effect is needed.
 */
export default function ApiKeyField({ provider, providerLabel, envVar, serverHasKey, onSaved }) {
  const stored = getKey(provider);
  const [value, setValue] = useState(stored);
  const [editing, setEditing] = useState(!stored);
  const [reveal, setReveal] = useState(false);
  const [saved, setSaved] = useState(false);

  const persist = (next) => {
    setKey(provider, next);
    setValue(next);
    setEditing(false);
    onSaved?.();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const remove = () => {
    clearKey(provider);
    setValue('');
    setEditing(true);
    setReveal(false);
    onSaved?.();
  };

  const usingOwnKey = Boolean(value);

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] font-medium text-ink-secondary">
          {providerLabel || provider} API key
        </span>
        {usingOwnKey ? (
          <Badge tone="buy" icon="check">Using your key</Badge>
        ) : serverHasKey ? (
          <Badge tone="accent" icon="key">Server key available</Badge>
        ) : (
          <Badge tone="hold" icon="alert">Key required</Badge>
        )}
      </div>

      {editing ? (
        <div className="flex flex-wrap gap-2">
          <Input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={envVar ? `${envVar} — paste your key` : 'Paste your API key'}
            className="min-w-[240px] flex-1 font-mono text-[12.5px]"
            autoComplete="off"
            spellCheck={false}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && value.trim()) {
                e.preventDefault();
                persist(value.trim());
              }
            }}
          />
          <Button icon="check" disabled={!value.trim()} onClick={() => persist(value.trim())}>
            Save
          </Button>
          {stored && (
            <Button variant="ghost" icon="x" onClick={() => { setValue(stored); setEditing(false); }}>
              Cancel
            </Button>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <code
            className={cx(
              'flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2',
              'font-mono text-[12.5px] break-all text-ink-secondary',
            )}
          >
            {reveal ? value : maskKey(value)}
          </code>
          <Button
            variant="ghost"
            size="sm"
            icon={reveal ? 'x' : 'search'}
            onClick={() => setReveal((r) => !r)}
          >
            {reveal ? 'Hide' : 'Show'}
          </Button>
          <Button variant="ghost" size="sm" icon="settings" onClick={() => setEditing(true)}>
            Change
          </Button>
          <Button variant="danger" size="sm" icon="trash" onClick={remove}>
            Remove
          </Button>
        </div>
      )}

      {saved && (
        <p className="flex items-center gap-1.5 text-[12px] text-buy">
          <Icon name="check" size={12} />
          Saved in this browser
        </p>
      )}

      <p className="text-[11.5px] leading-relaxed text-ink-muted">
        Stored in this browser only and sent with each analysis you start. It is never
        written to the server&apos;s database, run history or logs. Clearing your browser
        data removes it.
      </p>

      {!usingOwnKey && !serverHasKey && (
        <Alert tone="hold" icon="key" title="No key available for this provider">
          Paste your own key above, or pick a provider the server already has configured.
          Without one the run will fail on its first call.
        </Alert>
      )}
    </div>
  );
}
