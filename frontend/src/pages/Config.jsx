import { useCallback, useEffect, useState } from 'react';
import {
  deleteSavedConfig,
  getConfig,
  listProviders,
  listSavedConfigs,
  saveConfig,
  updateConfig,
} from '../lib/api';
import { classNames as cx } from '../lib/format';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Switch,
  Tabs,
} from '../components/ui';
import { useToast } from '../hooks/useToast';

/**
 * Config keys grouped for editing. Anything the backend returns that is not
 * listed here still shows up under "Other", so a new option added server-side
 * is never silently unreachable from the UI.
 */
const GROUPS = [
  {
    id: 'llm',
    label: 'Models',
    icon: 'cpu',
    keys: [
      'llm_provider',
      'deep_think_llm',
      'quick_think_llm',
      'backend_url',
      'output_language',
      'openai_reasoning_effort',
      'anthropic_effort',
      'google_thinking_level',
    ],
  },
  {
    id: 'debate',
    label: 'Debate',
    icon: 'scale',
    keys: ['max_debate_rounds', 'max_risk_discuss_rounds', 'max_recur_limit'],
  },
  {
    id: 'data',
    label: 'Data',
    icon: 'layers',
    keys: [
      'news_article_limit',
      'global_news_article_limit',
      'global_news_lookback_days',
      'data_vendors',
      'tool_vendors',
      'benchmark_ticker',
    ],
  },
  {
    id: 'storage',
    label: 'Storage',
    icon: 'history',
    keys: [
      'results_dir',
      'data_cache_dir',
      'memory_log_path',
      'memory_log_max_entries',
      'checkpoint_enabled',
      'project_dir',
    ],
  },
];

const DESCRIPTIONS = {
  llm_provider: 'Which provider new runs default to.',
  deep_think_llm: 'Model for the Research Manager, Trader and Portfolio Manager.',
  quick_think_llm: 'Model for analysts, researchers and risk debaters.',
  backend_url: 'Custom API endpoint. Blank uses each provider’s own default.',
  output_language: 'Language for reports and the final call.',
  openai_reasoning_effort: 'OpenAI reasoning effort — low, medium, high.',
  anthropic_effort: 'Claude effort level — low, medium, high.',
  google_thinking_level: 'Gemini thinking level — minimal through high.',
  max_debate_rounds: 'Bull/bear rounds. One round is two exchanges.',
  max_risk_discuss_rounds: 'Risk committee rounds. One round is three exchanges.',
  max_recur_limit: 'LangGraph recursion ceiling — raise only if long runs abort.',
  news_article_limit: 'Maximum articles fetched per ticker.',
  global_news_article_limit: 'Maximum macro/global articles.',
  global_news_lookback_days: 'How far back macro news is gathered.',
  data_vendors: 'Vendor per data category, with automatic fallback on rate limits.',
  tool_vendors: 'Per-tool vendor overrides, taking precedence over the category.',
  benchmark_ticker: 'Force one alpha benchmark. Blank auto-detects from the exchange suffix.',
  results_dir: 'Where run results are written.',
  data_cache_dir: 'Where fetched data and checkpoints are cached.',
  memory_log_path: 'The decision log the Memory page reads.',
  memory_log_max_entries: 'Cap on resolved log entries. Blank keeps everything.',
  checkpoint_enabled: 'Save state after each agent so a crashed run can resume.',
  project_dir: 'Framework install location — read only.',
};

const READ_ONLY = new Set(['project_dir']);

export default function Config() {
  const [config, setConfig] = useState({});
  const [original, setOriginal] = useState({});
  const [presets, setPresets] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('llm');
  const [presetName, setPresetName] = useState('');
  const [pendingDelete, setPendingDelete] = useState(null);
  const toast = useToast();

  const fetchAll = useCallback(
    () =>
      Promise.all([getConfig(), listSavedConfigs(), listProviders()])
        .then(([cfg, saved, provs]) => {
          setConfig(cfg.config);
          setOriginal(cfg.config);
          setPresets(saved);
          setProviders(provs);
          setError(null);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const load = () => {
    setLoading(true);
    fetchAll();
  };

  const dirty = JSON.stringify(config) !== JSON.stringify(original);

  const setValue = (key, value) => setConfig((c) => ({ ...c, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await updateConfig(config);
      setConfig(res.config);
      setOriginal(res.config);
      toast.push('Configuration applied');
    } catch (err) {
      toast.push(err.message, 'danger');
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreset = async () => {
    const name = presetName.trim();
    if (!name) return;
    try {
      await saveConfig(name, config);
      setPresets(await listSavedConfigs());
      setPresetName('');
      toast.push(`Preset "${name}" saved`);
    } catch (err) {
      toast.push(err.message, 'danger');
    }
  };

  const handleDeletePreset = async () => {
    if (!pendingDelete) return;
    try {
      await deleteSavedConfig(pendingDelete.id);
      setPresets(await listSavedConfigs());
      setPendingDelete(null);
      toast.push('Preset deleted');
    } catch (err) {
      toast.push(err.message, 'danger');
    }
  };

  const applyPreset = (preset) => {
    setConfig((c) => ({ ...c, ...preset.config_json }));
    toast.push(`Loaded "${preset.name}" — review, then apply`);
  };

  // Keys the backend returned that no group claims.
  const grouped = new Set(GROUPS.flatMap((g) => g.keys));
  const otherKeys = Object.keys(config).filter((k) => !grouped.has(k));

  const tabs = [
    ...GROUPS.map((g) => ({ value: g.id, label: g.label, icon: g.icon })),
    ...(otherKeys.length ? [{ value: 'other', label: 'Other', icon: 'settings' }] : []),
    { value: 'keys', label: 'API keys', icon: 'key' },
    { value: 'presets', label: 'Presets', icon: 'layers', count: presets.length },
  ];

  const activeKeys =
    tab === 'other' ? otherKeys : GROUPS.find((g) => g.id === tab)?.keys.filter((k) => k in config);

  return (
    <div className="space-y-5">
      {toast.view}

      <PageHeader
        title="Configuration"
        description="Defaults for new runs. Changes apply to the running server, not to runs already in flight."
      >
        {dirty && (
          <Button size="sm" icon="refresh" onClick={() => setConfig(original)}>
            Discard
          </Button>
        )}
        <Button
          variant="primary"
          size="sm"
          icon="check"
          onClick={handleSave}
          loading={saving}
          disabled={!dirty}
        >
          {dirty ? 'Apply changes' : 'No changes'}
        </Button>
      </PageHeader>

      {error && (
        <Alert title="Could not load configuration" action={<Button size="sm" onClick={load}>Retry</Button>}>
          {error}
        </Alert>
      )}

      <Alert tone="hold" icon="info" title="These changes are in-memory">
        Configuration is applied to the running backend process and is lost when it restarts. Save a
        preset to keep a set of values, or set the matching{' '}
        <code className="font-mono">MARKETMINDS_*</code> environment variables to make them
        permanent.
      </Alert>

      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {loading ? (
        <Card>
          <LoadingRows rows={6} />
        </Card>
      ) : tab === 'presets' ? (
        <PresetsPanel
          presets={presets}
          presetName={presetName}
          setPresetName={setPresetName}
          onSave={handleSavePreset}
          onApply={applyPreset}
          onDelete={setPendingDelete}
        />
      ) : tab === 'keys' ? (
        <KeysPanel providers={providers} />
      ) : (
        <Card>
          <CardHeader
            title={tabs.find((t) => t.value === tab)?.label}
            icon={tabs.find((t) => t.value === tab)?.icon}
            description={`${activeKeys?.length || 0} settings`}
          />
          {activeKeys?.length ? (
            <div className="divide-y divide-line">
              {activeKeys.map((key) => (
                <ConfigRow
                  key={key}
                  name={key}
                  value={config[key]}
                  description={DESCRIPTIONS[key]}
                  readOnly={READ_ONLY.has(key)}
                  onChange={(v) => setValue(key, v)}
                />
              ))}
            </div>
          ) : (
            <EmptyState icon="settings" title="No settings in this group" />
          )}
        </Card>
      )}

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={`Delete preset "${pendingDelete?.name}"?`}
        description="The saved values are removed. Your current configuration is unaffected."
        footer={
          <>
            <Button size="sm" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" icon="trash" onClick={handleDeletePreset}>
              Delete preset
            </Button>
          </>
        }
      />
    </div>
  );
}

/** One setting, rendered by the type of its current value. */
function ConfigRow({ name, value, description, readOnly, onChange }) {
  const isBool = typeof value === 'boolean';
  const isNumber = typeof value === 'number';
  const isObject = value !== null && typeof value === 'object';

  return (
    <div className="grid gap-3 px-5 py-3.5 lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
      <div className="min-w-0">
        <p className="font-mono text-[12.5px] font-medium text-ink">{name}</p>
        {description && (
          <p className="mt-0.5 text-[12px] leading-snug text-ink-muted">{description}</p>
        )}
      </div>

      <div className="min-w-0">
        {isBool ? (
          <Switch id={name} checked={value} onChange={onChange} disabled={readOnly} />
        ) : isObject ? (
          <ObjectEditor value={value} onChange={onChange} readOnly={readOnly} />
        ) : (
          <Input
            value={value ?? ''}
            type={isNumber ? 'number' : 'text'}
            readOnly={readOnly}
            placeholder={value === null ? 'not set' : ''}
            className={cx(
              'font-mono text-[12.5px]',
              readOnly && 'cursor-not-allowed opacity-60',
            )}
            onChange={(e) => {
              const raw = e.target.value;
              if (raw === '') onChange(null);
              else onChange(isNumber ? Number(raw) : raw);
            }}
          />
        )}
      </div>
    </div>
  );
}

/** Flat key/value editor for dict-valued settings like `data_vendors`. */
function ObjectEditor({ value, onChange, readOnly }) {
  const entries = Object.entries(value || {});

  if (!entries.length) {
    return <p className="text-[12.5px] text-ink-muted">Empty — no overrides set.</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([key, val]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="w-44 shrink-0 truncate font-mono text-[12px] text-ink-secondary">
            {key}
          </span>
          <Input
            value={typeof val === 'object' ? JSON.stringify(val) : (val ?? '')}
            readOnly={readOnly}
            className="font-mono text-[12.5px]"
            onChange={(e) => onChange({ ...value, [key]: e.target.value })}
          />
        </div>
      ))}
    </div>
  );
}

function PresetsPanel({ presets, presetName, setPresetName, onSave, onApply, onDelete }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Save current configuration"
          icon="layers"
          description="Presets persist in the database and survive a restart"
        />
        <div className="flex flex-wrap gap-2 px-5 py-4">
          <Input
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            placeholder="e.g. Fast and cheap"
            className="max-w-xs flex-1"
            onKeyDown={(e) => e.key === 'Enter' && onSave()}
          />
          <Button variant="primary" icon="check" onClick={onSave} disabled={!presetName.trim()}>
            Save preset
          </Button>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Saved presets" icon="history" />
        {presets.length === 0 ? (
          <EmptyState
            icon="layers"
            title="No presets yet"
            description="Save your current settings above to reuse them later."
          />
        ) : (
          <ul className="divide-y divide-line">
            {presets.map((preset) => (
              <li key={preset.id} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-ink">{preset.name}</p>
                  <p className="truncate font-mono text-[11.5px] text-ink-muted">
                    {Object.keys(preset.config_json || {}).length} keys
                  </p>
                </div>
                <Button size="sm" icon="download" onClick={() => onApply(preset)}>
                  Load
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${preset.name}`}
                  className="hover:text-danger"
                  onClick={() => onDelete(preset)}
                >
                  <Icon name="trash" size={14} />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/** Which providers are actually usable right now, and which env var is missing. */
function KeysPanel({ providers }) {
  const ready = providers.filter((p) => p.has_key).length;

  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Provider keys"
        icon="key"
        description="Read from the backend's environment — set them in .env and restart to change"
        action={
          <Badge tone={ready ? 'buy' : 'hold'}>
            {ready} of {providers.length} ready
          </Badge>
        }
      />
      <ul className="divide-y divide-line">
        {providers.map((provider) => (
          <li key={provider.name} className="flex items-center gap-3 px-5 py-2.5">
            <span
              className={cx(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border',
                provider.has_key
                  ? 'border-buy-border bg-buy-soft text-buy'
                  : 'border-line bg-surface-2 text-ink-muted',
              )}
            >
              <Icon name={provider.has_key ? 'check' : 'key'} size={13} />
            </span>

            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-ink">{provider.display_name}</p>
              <p className="truncate font-mono text-[11.5px] text-ink-muted">
                {provider.env_var || 'no key required'}
              </p>
            </div>

            <Badge tone={provider.has_key ? 'buy' : provider.requires_key ? 'neutral' : 'accent'}>
              {provider.has_key ? 'ready' : provider.requires_key ? 'missing key' : 'local'}
            </Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}
