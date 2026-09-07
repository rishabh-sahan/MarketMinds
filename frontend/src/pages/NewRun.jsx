import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { createRun, getProviderModels, listProviders } from '../lib/api';
import { getKey } from '../lib/apiKeys';
import { useAuth } from '../lib/auth-context';
import ApiKeyField from '../components/ApiKeyField';
import { classNames as cx, todayISO } from '../lib/format';
import {
  ANALYSTS,
  DATA_VENDORS,
  DATA_VENDOR_CATEGORIES,
  EFFORT_PROVIDERS,
  OUTPUT_LANGUAGES,
} from '../lib/pipeline';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  Switch,
} from '../components/ui';

/** The catalog uses this sentinel to mean "let me type a model id". */
const CUSTOM = 'custom';

const INITIAL = {
  ticker: '',
  trade_date: todayISO(),
  llm_provider: 'openai',
  quick_think_llm: '',
  deep_think_llm: '',
  selected_analysts: ANALYSTS.map((a) => a.key),
  max_debate_rounds: 1,
  max_risk_discuss_rounds: 1,
  output_language: 'English',
  backend_url: '',
  reasoning_effort: '',
  checkpoint_enabled: false,
  data_vendors: {},
  news_article_limit: '',
  global_news_article_limit: '',
  global_news_lookback_days: '',
};

export default function NewRun() {
  const navigate = useNavigate();
  const { enabled: authEnabled, loading: authLoading, signedIn, signIn } = useAuth();
  // Only block once we actually know: while the session is resolving,
  // showing the sign-in prompt would flash it at users who are signed in.
  const needsSignIn = authEnabled && !authLoading && !signedIn;
  const [searchParams] = useSearchParams();
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState({ quick: [], deep: [] });
  const [modelsLoading, setModelsLoading] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  // The landing page hands the typed symbol over as ?ticker=.
  const [form, setForm] = useState(() => ({
    ...INITIAL,
    ticker: (searchParams.get('ticker') || '').toUpperCase(),
  }));

  // Free-text model ids, used when the dropdown is set to "Custom model ID".
  const [customModel, setCustomModel] = useState({ quick: '', deep: '' });

  // The visitor's own provider key, read from this browser. Derived rather
  // than stored: the counter bumps when the field saves, which re-reads
  // storage without an effect. Never persisted server-side.
  const [, bumpKeyVersion] = useState(0);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    listProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  const providerId = form.llm_provider;

  useEffect(() => {
    if (!providerId) return undefined;
    let stale = false;

    const loadModels = async () => {
      setModelsLoading(true);
      try {
        const data = await getProviderModels(providerId);
        if (stale) return;
        setModels(data);
        // Default to the first option each time the provider changes, since a
        // model id from one provider is meaningless to another.
        setForm((f) => ({
          ...f,
          quick_think_llm: data.quick[0]?.value || '',
          deep_think_llm: data.deep[0]?.value || '',
          reasoning_effort: '',
        }));
        setCustomModel({ quick: '', deep: '' });
      } catch {
        if (!stale) setModels({ quick: [], deep: [] });
      } finally {
        if (!stale) setModelsLoading(false);
      }
    };

    loadModels();
    return () => {
      stale = true;
    };
  }, [providerId]);

  const provider = providers.find((p) => p.name === form.llm_provider);
  // Read straight from browser storage on each render. `keyVersion` exists
  // only to force that render after the field saves — memoising here would
  // mean lying to the dependency checker about reading external state.
  const apiKey = getKey(form.llm_provider);
  const effortConfig = EFFORT_PROVIDERS[form.llm_provider];

  const toggleAnalyst = (key) =>
    setForm((f) => ({
      ...f,
      selected_analysts: f.selected_analysts.includes(key)
        ? f.selected_analysts.filter((a) => a !== key)
        : [...f.selected_analysts, key],
    }));

  // The value actually sent for each model slot, resolving the custom sentinel.
  const resolvedModels = useMemo(
    () => ({
      quick: form.quick_think_llm === CUSTOM ? customModel.quick.trim() : form.quick_think_llm,
      deep: form.deep_think_llm === CUSTOM ? customModel.deep.trim() : form.deep_think_llm,
    }),
    [form.quick_think_llm, form.deep_think_llm, customModel],
  );

  const validate = () => {
    if (!form.ticker.trim()) return 'Enter a ticker symbol.';
    if (provider?.requires_key && !apiKey && !provider.has_key) {
      return `Add your ${provider.display_name} API key, or choose a provider the server has configured.`;
    }
    if (!form.trade_date) return 'Pick an analysis date.';
    if (!form.selected_analysts.length) return 'Select at least one analyst.';
    if (!resolvedModels.quick) return 'Enter the custom quick-thinking model id.';
    if (!resolvedModels.deep) return 'Enter the custom deep-thinking model id.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }

    setSubmitting(true);
    setError(null);

    // Blank advanced fields are omitted so the backend keeps its own defaults.
    const optionalInt = (v) => (v === '' || v == null ? null : Number(v));
    const payload = {
      ticker: form.ticker.trim().toUpperCase(),
      trade_date: form.trade_date,
      llm_provider: form.llm_provider,
      quick_think_llm: resolvedModels.quick,
      deep_think_llm: resolvedModels.deep,
      selected_analysts: form.selected_analysts,
      max_debate_rounds: Number(form.max_debate_rounds),
      max_risk_discuss_rounds: Number(form.max_risk_discuss_rounds),
      output_language: form.output_language,
      // Sent per run, used for that run, stored nowhere.
      api_key: apiKey || null,
      backend_url: form.backend_url.trim() || null,
      reasoning_effort: form.reasoning_effort || null,
      checkpoint_enabled: form.checkpoint_enabled,
      data_vendors: Object.keys(form.data_vendors).length ? form.data_vendors : null,
      news_article_limit: optionalInt(form.news_article_limit),
      global_news_article_limit: optionalInt(form.global_news_article_limit),
      global_news_lookback_days: optionalInt(form.global_news_lookback_days),
    };

    try {
      const run = await createRun(payload);
      navigate(`/runs/${run.id}/live`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <PageHeader
        title="New analysis"
        description="Configure the desk, then let the agents debate their way to a rating."
      />

      {error && <Alert title="Cannot start the run">{error}</Alert>}


      {/* ------------------------------------------------------- instrument */}
      <Card>
        <CardHeader title="Instrument" icon="target" description="What to analyse, and as of when" />
        <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
          <Field
            label="Ticker symbol"
            htmlFor="ticker"
            hint="NSE or BSE listing. A bare name resolves to NSE — RELIANCE, TCS, HDFCBANK.NS"
          >
            <Input
              id="ticker"
              value={form.ticker}
              onChange={(e) => set({ ticker: e.target.value.toUpperCase() })}
              placeholder="RELIANCE"
              className="font-mono"
              autoComplete="off"
              autoFocus
            />
          </Field>
          <Field
            label="Analysis date"
            htmlFor="trade_date"
            hint="Agents reason as of this date; later prices resolve the outcome"
          >
            <Input
              id="trade_date"
              type="date"
              value={form.trade_date}
              max={todayISO()}
              onChange={(e) => set({ trade_date: e.target.value })}
            />
          </Field>
        </div>
      </Card>

      {/* ------------------------------------------------------------ model */}
      <Card>
        <CardHeader
          title="Models"
          icon="cpu"
          description="A quick model for the analysts, a deep one for the decision makers"
          action={
            provider && (
              <Badge
                tone={apiKey ? 'buy' : provider.has_key ? 'accent' : 'hold'}
                icon="key"
              >
                {apiKey ? 'Your key' : provider.has_key ? 'Server key' : 'No key'}
              </Badge>
            )
          }
        />
        <div className="grid gap-4 px-5 py-4 lg:grid-cols-3">
          <Field label="Provider" htmlFor="provider">
            <Select
              id="provider"
              value={form.llm_provider}
              onChange={(e) => set({ llm_provider: e.target.value })}
            >
              {providers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.display_name}
                  {p.requires_key && !p.has_key ? ' — no key' : ''}
                </option>
              ))}
            </Select>
          </Field>

          <ModelPicker
            label="Quick thinking"
            id="quick_model"
            hint="Analysts, researchers, risk debaters"
            options={models.quick}
            loading={modelsLoading}
            value={form.quick_think_llm}
            onChange={(v) => set({ quick_think_llm: v })}
            customValue={customModel.quick}
            onCustomChange={(v) => setCustomModel((c) => ({ ...c, quick: v }))}
          />

          <ModelPicker
            label="Deep thinking"
            id="deep_model"
            hint="Research Manager, Trader, Portfolio Manager"
            options={models.deep}
            loading={modelsLoading}
            value={form.deep_think_llm}
            onChange={(v) => set({ deep_think_llm: v })}
            customValue={customModel.deep}
            onCustomChange={(v) => setCustomModel((c) => ({ ...c, deep: v }))}
          />
        </div>

        {provider?.requires_key && (
          <div className="border-t border-line px-5 py-4">
            <ApiKeyField
              key={form.llm_provider}
              provider={form.llm_provider}
              providerLabel={provider.display_name}
              envVar={provider.env_var}
              serverHasKey={provider.has_key}
              onSaved={() => bumpKeyVersion((v) => v + 1)}
            />
          </div>
        )}
      </Card>

      {/* --------------------------------------------------------- analysts */}
      <Card>
        <CardHeader
          title="Analyst team"
          icon="layers"
          description="Each analyst runs its own tool loop before writing a report"
          action={
            <span className="text-[12.5px] text-ink-muted">
              {form.selected_analysts.length} of {ANALYSTS.length} selected
            </span>
          }
        />
        <div className="grid gap-3 px-5 py-4 sm:grid-cols-2">
          {ANALYSTS.map((analyst) => {
            const selected = form.selected_analysts.includes(analyst.key);
            return (
              <button
                key={analyst.key}
                type="button"
                onClick={() => toggleAnalyst(analyst.key)}
                aria-pressed={selected}
                className={cx(
                  'flex items-start gap-3 rounded-xl border p-3.5 text-left transition-all duration-150',
                  selected
                    ? 'border-accent-border bg-accent-soft shadow-sm'
                    : 'border-line bg-surface hover:border-line-strong hover:bg-surface-2',
                )}
              >
                <span
                  className={cx(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
                    selected
                      ? 'border-accent-border bg-surface text-accent'
                      : 'border-line bg-surface-2 text-ink-muted',
                  )}
                >
                  <Icon name={analyst.icon} size={15} />
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-semibold text-ink">{analyst.agent}</span>
                  <span className="mt-0.5 block text-[12px] leading-snug text-ink-muted">
                    {analyst.blurb}
                  </span>
                </span>

                <span
                  className={cx(
                    'flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded border transition-colors',
                    selected
                      ? 'border-accent bg-accent text-on-accent'
                      : 'border-line-strong bg-surface',
                  )}
                >
                  {selected && <Icon name="check" size={11} strokeWidth={2.6} />}
                </span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* ----------------------------------------------------------- debate */}
      <Card>
        <CardHeader
          title="Debate depth"
          icon="scale"
          description="More rounds means deeper argument, more tokens, and a longer run"
        />
        <div className="grid gap-4 px-5 py-4 lg:grid-cols-3">
          <Field
            label="Bull / bear rounds"
            htmlFor="debate_rounds"
            hint="One round is two exchanges"
          >
            <Select
              id="debate_rounds"
              value={form.max_debate_rounds}
              onChange={(e) => set({ max_debate_rounds: Number(e.target.value) })}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} round{n > 1 ? 's' : ''}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Risk committee rounds"
            htmlFor="risk_rounds"
            hint="One round is three exchanges"
          >
            <Select
              id="risk_rounds"
              value={form.max_risk_discuss_rounds}
              onChange={(e) => set({ max_risk_discuss_rounds: Number(e.target.value) })}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} round{n > 1 ? 's' : ''}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Output language"
            htmlFor="language"
            hint="Reports and the final call; internal debate stays in English"
          >
            <Select
              id="language"
              value={form.output_language}
              onChange={(e) => set({ output_language: e.target.value })}
            >
              {OUTPUT_LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {/* --------------------------------------------------------- advanced */}
      <Card>
        <button
          type="button"
          onClick={() => setAdvanced((a) => !a)}
          className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition-colors hover:bg-surface-2"
          aria-expanded={advanced}
        >
          <span>
            <span className="flex items-center gap-2 text-[14px] font-semibold tracking-tight text-ink">
              <Icon name="settings" size={15} className="text-ink-muted" />
              Advanced
            </span>
            <span className="mt-0.5 block text-[12.5px] text-ink-muted">
              Endpoint, reasoning budget, data vendors, checkpointing
            </span>
          </span>
          <Icon
            name="chevronDown"
            size={16}
            className={cx('shrink-0 text-ink-muted transition-transform', advanced && 'rotate-180')}
          />
        </button>

        {advanced && (
          <div className="animate-fade space-y-5 border-t border-line px-5 py-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <Field
                label="Custom endpoint URL"
                htmlFor="backend_url"
                hint="For a self-hosted or proxied OpenAI-compatible endpoint. Blank uses the provider default."
              >
                <Input
                  id="backend_url"
                  value={form.backend_url}
                  onChange={(e) => set({ backend_url: e.target.value })}
                  placeholder="http://localhost:11434/v1"
                  className="font-mono text-[12.5px]"
                />
              </Field>

              <Field
                label={effortConfig ? effortConfig.label : 'Reasoning effort'}
                htmlFor="effort"
                hint={
                  effortConfig
                    ? 'Higher settings reason longer and cost more.'
                    : `${provider?.display_name || 'This provider'} exposes no thinking control.`
                }
              >
                <Select
                  id="effort"
                  value={form.reasoning_effort}
                  disabled={!effortConfig}
                  onChange={(e) => set({ reasoning_effort: e.target.value })}
                >
                  <option value="">Provider default</option>
                  {(effortConfig?.options || []).map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <div>
              <p className="mb-2 text-[12.5px] font-medium text-ink-secondary">Data vendors</p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {DATA_VENDOR_CATEGORIES.map((cat) => (
                  <Field key={cat.key} label={cat.label} htmlFor={`vendor-${cat.key}`}>
                    <Select
                      id={`vendor-${cat.key}`}
                      value={form.data_vendors[cat.key] || ''}
                      onChange={(e) => {
                        const next = { ...form.data_vendors };
                        if (e.target.value) next[cat.key] = e.target.value;
                        else delete next[cat.key];
                        set({ data_vendors: next });
                      }}
                    >
                      <option value="">Default</option>
                      {DATA_VENDORS.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="News articles per ticker" htmlFor="news_limit" hint="Default 20">
                <Input
                  id="news_limit"
                  type="number"
                  min="1"
                  max="100"
                  value={form.news_article_limit}
                  onChange={(e) => set({ news_article_limit: e.target.value })}
                  placeholder="20"
                />
              </Field>
              <Field label="Macro articles" htmlFor="global_limit" hint="Default 10">
                <Input
                  id="global_limit"
                  type="number"
                  min="1"
                  max="100"
                  value={form.global_news_article_limit}
                  onChange={(e) => set({ global_news_article_limit: e.target.value })}
                  placeholder="10"
                />
              </Field>
              <Field label="Macro lookback (days)" htmlFor="lookback" hint="Default 7">
                <Input
                  id="lookback"
                  type="number"
                  min="1"
                  max="90"
                  value={form.global_news_lookback_days}
                  onChange={(e) => set({ global_news_lookback_days: e.target.value })}
                  placeholder="7"
                />
              </Field>
            </div>

            <Switch
              id="checkpoint"
              checked={form.checkpoint_enabled}
              onChange={(v) => set({ checkpoint_enabled: v })}
              label="Checkpoint resume"
              hint="Save state after each agent so an interrupted run resumes instead of restarting."
            />
          </div>
        )}
      </Card>

      {/* ----------------------------------------------------------- submit */}
      {/* Sign-in is required only here. Everything above can be configured
          signed out, so a visitor is not asked to authenticate before they
          have seen what they would be authenticating for. */}
      {needsSignIn ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent-border bg-accent-soft px-5 py-4">
          <div className="min-w-0">
            <p className="text-[13.5px] font-medium text-ink">Sign in to run this analysis</p>
            <p className="mt-0.5 text-[12.5px] text-ink-secondary">
              Your runs stay private to your account. Your API key stays in this browser.
            </p>
          </div>
          <Button variant="primary" size="lg" onClick={signIn}>
            Continue with Google
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-5 py-4 shadow-sm">
          <p className="text-[12.5px] text-ink-muted">
            A full run takes several minutes. You can watch every agent as it works.
          </p>
          <Button type="submit" variant="primary" size="lg" icon="play" loading={submitting}>
            {submitting ? 'Starting…' : 'Start analysis'}
          </Button>
        </div>
      )}
    </form>
  );
}

/**
 * Model dropdown that swaps to a free-text field when "Custom model ID" is
 * chosen — the catalog's sentinel value is not itself a valid model id.
 */
function ModelPicker({
  label,
  id,
  hint,
  options,
  loading,
  value,
  onChange,
  customValue,
  onCustomChange,
}) {
  const isCustom = value === CUSTOM;

  return (
    <Field label={label} htmlFor={id} hint={isCustom ? 'Enter the exact model id.' : hint}>
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={loading}>
        {loading && <option>Loading models…</option>}
        {!loading && options.length === 0 && <option value="">No models available</option>}
        {options.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </Select>
      {isCustom && (
        <Input
          value={customValue}
          onChange={(e) => onCustomChange(e.target.value)}
          placeholder="llama3.1:70b"
          className="mt-2 font-mono text-[12.5px]"
        />
      )}
    </Field>
  );
}
