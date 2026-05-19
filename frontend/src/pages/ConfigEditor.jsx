import { useState, useEffect } from 'react';
import { getConfig, updateConfig, listSavedConfigs, saveConfig, deleteSavedConfig } from '../services/api';
import './ConfigEditor.css';

const CONFIG_GROUPS = {
  'LLM Settings': ['llm_provider', 'deep_think_llm', 'quick_think_llm', 'backend_url', 'output_language'],
  'Thinking Config': ['google_thinking_level', 'openai_reasoning_effort', 'anthropic_effort'],
  'Debate Settings': ['max_debate_rounds', 'max_risk_discuss_rounds', 'max_recur_limit'],
  'News & Data': ['news_article_limit', 'global_news_article_limit', 'global_news_lookback_days'],
  'Paths': ['results_dir', 'data_cache_dir', 'memory_log_path'],
  'Checkpointing': ['checkpoint_enabled'],
  'Benchmark': ['benchmark_ticker'],
};

const CONFIG_DESCRIPTIONS = {
  llm_provider: 'LLM provider (openai, anthropic, google, xai, deepseek, ollama, etc.)',
  deep_think_llm: 'Model for complex reasoning (Research Manager, Portfolio Manager)',
  quick_think_llm: 'Model for fast tasks (analysts, debaters)',
  backend_url: 'Custom API endpoint (null = provider default)',
  output_language: 'Language for analyst reports and final decision',
  google_thinking_level: 'Gemini thinking mode (high, minimal, etc.)',
  openai_reasoning_effort: 'OpenAI reasoning effort (low, medium, high)',
  anthropic_effort: 'Claude effort level (low, medium, high)',
  max_debate_rounds: 'Number of Bull/Bear debate rounds (1 round = 2 exchanges)',
  max_risk_discuss_rounds: 'Number of risk team debate rounds (1 round = 3 exchanges)',
  max_recur_limit: 'Maximum LangGraph recursion limit',
  news_article_limit: 'Max articles per ticker for news fetching',
  global_news_article_limit: 'Max articles for global/macro news',
  global_news_lookback_days: 'Macro news lookback window in days',
  results_dir: 'Directory for saving run results',
  data_cache_dir: 'Directory for data caching',
  memory_log_path: 'Path to the trading memory log file',
  checkpoint_enabled: 'Enable crash-resume via SQLite checkpointing',
  benchmark_ticker: 'Benchmark ticker for alpha calculation (null = auto-detect)',
};

export default function ConfigEditor() {
  const [config, setConfig] = useState({});
  const [savedConfigs, setSavedConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [message, setMessage] = useState(null);

  useEffect(() => {
    Promise.all([getConfig(), listSavedConfigs()])
      .then(([cfg, saved]) => {
        setConfig(cfg.config);
        setSavedConfigs(saved);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateConfig(config);
      setMessage({ type: 'success', text: 'Config updated successfully!' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    }
    setSaving(false);
    setTimeout(() => setMessage(null), 3000);
  };

  const handleSavePreset = async () => {
    if (!presetName.trim()) return;
    try {
      await saveConfig(presetName, config);
      const saved = await listSavedConfigs();
      setSavedConfigs(saved);
      setPresetName('');
      setMessage({ type: 'success', text: `Preset "${presetName}" saved!` });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    }
    setTimeout(() => setMessage(null), 3000);
  };

  const handleLoadPreset = (preset) => {
    setConfig(preset.config_json);
    setMessage({ type: 'success', text: `Loaded preset "${preset.name}"` });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleDeletePreset = async (id) => {
    try {
      await deleteSavedConfig(id);
      setSavedConfigs(prev => prev.filter(p => p.id !== id));
    } catch {}
  };

  const renderInput = (key, value) => {
    if (typeof value === 'boolean') {
      return (
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={value}
            onChange={(e) => handleChange(key, e.target.checked)}
          />
          <span className="toggle-switch" />
          <span className="text-sm">{value ? 'Enabled' : 'Disabled'}</span>
        </label>
      );
    }
    if (typeof value === 'number') {
      return (
        <input
          className="input"
          type="number"
          value={value}
          onChange={(e) => handleChange(key, parseInt(e.target.value) || 0)}
        />
      );
    }
    if (value === null || value === undefined) {
      return (
        <input
          className="input"
          type="text"
          value=""
          placeholder="null"
          onChange={(e) => handleChange(key, e.target.value || null)}
        />
      );
    }
    return (
      <input
        className="input"
        type="text"
        value={value}
        onChange={(e) => handleChange(key, e.target.value)}
      />
    );
  };

  if (loading) {
    return (
      <div className="config-page">
        <div className="empty-state"><div className="spinner" /><p className="text-muted">Loading config...</p></div>
      </div>
    );
  }

  return (
    <div className="config-page">
      <div className="page-header">
        <div>
          <h1>Configuration</h1>
          <p className="text-muted">Edit runtime settings for the TradingAgents framework</p>
        </div>
        <div className="flex gap-sm">
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : '💾 Save Config'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`config-message ${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="config-layout">
        {/* Main Config */}
        <div className="config-main">
          {Object.entries(CONFIG_GROUPS).map(([group, keys]) => {
            const activeKeys = keys.filter(k => k in config);
            if (activeKeys.length === 0) return null;
            return (
              <div key={group} className="config-group glass-card">
                <h3 className="config-group-title">{group}</h3>
                <div className="config-fields">
                  {activeKeys.map(key => (
                    <div key={key} className="config-field">
                      <div className="config-field-header">
                        <label className="config-key font-mono text-sm">{key}</label>
                        {CONFIG_DESCRIPTIONS[key] && (
                          <span className="config-desc text-xs text-muted">{CONFIG_DESCRIPTIONS[key]}</span>
                        )}
                      </div>
                      {renderInput(key, config[key])}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Presets Sidebar */}
        <div className="config-sidebar">
          <div className="presets-card glass-card">
            <h3>Saved Presets</h3>
            <div className="preset-save">
              <input
                className="input"
                type="text"
                placeholder="Preset name..."
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
              />
              <button className="btn btn-secondary btn-sm" onClick={handleSavePreset}>Save As</button>
            </div>
            {savedConfigs.length === 0 ? (
              <p className="text-muted text-sm" style={{ padding: '12px 0' }}>No saved presets yet.</p>
            ) : (
              <div className="presets-list">
                {savedConfigs.map(preset => (
                  <div key={preset.id} className="preset-item">
                    <button className="preset-name btn btn-ghost btn-sm" onClick={() => handleLoadPreset(preset)}>
                      {preset.name}
                    </button>
                    <button className="preset-delete btn btn-ghost btn-sm" onClick={() => handleDeletePreset(preset.id)}>
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
