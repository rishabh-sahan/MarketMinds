/**
 * The agent pipeline, mirrored from the backend.
 *
 * Agent names here must match `backend/services/run_tracker.py` exactly — they
 * are the keys the WebSocket sends for every status transition. The phases and
 * copy are presentation only.
 */

/** The four selectable analysts, keyed by the value the API expects. */
export const ANALYSTS = [
  {
    key: 'market',
    agent: 'Market Analyst',
    icon: 'chart',
    blurb: 'Picks up to 8 complementary technical indicators, read against the Nifty, sector indices, India VIX and the rupee.',
    short: 'Technicals vs the Nifty & sectors',
    reportKey: 'market_report',
  },
  {
    key: 'social',
    agent: 'Sentiment Analyst',
    icon: 'chat',
    blurb: 'Reads company coverage from Indian media against the front pages of the domestic financial press, separating the company\'s story from the market mood.',
    short: 'Indian media & press sentiment',
    reportKey: 'sentiment_report',
  },
  {
    key: 'news',
    agent: 'News Analyst',
    icon: 'news',
    blurb: 'RBI and SEBI policy, Budget and GST, inflation and GDP prints, FII/DII flows, index rejigs, sector news and exchange filings.',
    short: 'RBI, SEBI, policy & filings',
    reportKey: 'news_report',
  },
  {
    key: 'fundamentals',
    agent: 'Fundamentals Analyst',
    icon: 'ledger',
    blurb: 'Balance sheet, cash flow, income statement and company profile — intrinsic value and red flags.',
    short: 'Financial statements & valuation',
    reportKey: 'fundamentals_report',
  },
];

export const ANALYST_KEYS = ANALYSTS.map((a) => a.key);

/** Every agent in pipeline order, with the phase it belongs to. */
export const PIPELINE = [
  ...ANALYSTS.map((a) => ({
    agent: a.agent,
    phase: 'Analysis',
    icon: a.icon,
    role: a.short,
    reportKey: a.reportKey,
    analystKey: a.key,
  })),
  {
    agent: 'Bull Researcher',
    phase: 'Research',
    icon: 'trendUp',
    role: 'Argues the bull case from the analyst reports',
    reportKey: 'bull_history',
  },
  {
    agent: 'Bear Researcher',
    phase: 'Research',
    icon: 'trendDown',
    role: 'Argues the bear case, answering the bull directly',
    reportKey: 'bear_history',
  },
  {
    agent: 'Research Manager',
    phase: 'Research',
    icon: 'gavel',
    role: 'Judges the debate and issues an investment plan',
    reportKey: 'investment_plan',
  },
  {
    agent: 'Trader',
    phase: 'Execution',
    icon: 'briefcase',
    role: 'Turns the plan into a concrete transaction proposal',
    reportKey: 'trader_investment_plan',
  },
  {
    agent: 'Aggressive Analyst',
    phase: 'Risk',
    icon: 'flame',
    role: 'Pushes for the higher-conviction, higher-reward path',
    reportKey: 'aggressive_history',
  },
  {
    agent: 'Conservative Analyst',
    phase: 'Risk',
    icon: 'shield',
    role: 'Stress-tests downside and capital preservation',
    reportKey: 'conservative_history',
  },
  {
    agent: 'Neutral Analyst',
    phase: 'Risk',
    icon: 'scale',
    role: 'Weighs both risk cases without a directional prior',
    reportKey: 'neutral_history',
  },
  {
    agent: 'Portfolio Manager',
    phase: 'Decision',
    icon: 'verdict',
    role: 'Synthesises the risk debate into the final rating',
    reportKey: 'final_trade_decision',
  },
];

/** Phase order, used to group the pipeline view. */
export const PHASES = ['Analysis', 'Research', 'Execution', 'Risk', 'Decision'];

export const PHASE_BLURBS = {
  Analysis: 'Four analysts gather evidence with their own tools',
  Research: 'Bull and bear argue; a manager rules',
  Execution: 'The plan becomes a transaction proposal',
  Risk: 'Three risk views rotate through the proposal',
  Decision: 'The final position rating',
};

/** Agent name → its pipeline entry. */
export const AGENT_BY_NAME = Object.fromEntries(PIPELINE.map((p) => [p.agent, p]));

/**
 * The report sections shown on a finished run, in reading order.
 * `path` walks `run.result_json`.
 */
export const REPORT_SECTIONS = [
  { key: 'market_report', title: 'Market Analyst', group: 'Analysis', path: ['market_report'] },
  { key: 'sentiment_report', title: 'Sentiment Analyst', group: 'Analysis', path: ['sentiment_report'] },
  { key: 'news_report', title: 'News Analyst', group: 'Analysis', path: ['news_report'] },
  { key: 'fundamentals_report', title: 'Fundamentals Analyst', group: 'Analysis', path: ['fundamentals_report'] },
  { key: 'bull_history', title: 'Bull Researcher', group: 'Debate', path: ['investment_debate', 'bull_history'] },
  { key: 'bear_history', title: 'Bear Researcher', group: 'Debate', path: ['investment_debate', 'bear_history'] },
  { key: 'investment_plan', title: 'Research Manager', group: 'Debate', path: ['investment_plan'] },
  { key: 'trader_investment_plan', title: 'Trader', group: 'Decision', path: ['trader_investment_plan'] },
  { key: 'aggressive_history', title: 'Aggressive Analyst', group: 'Risk', path: ['risk_debate', 'aggressive_history'] },
  { key: 'conservative_history', title: 'Conservative Analyst', group: 'Risk', path: ['risk_debate', 'conservative_history'] },
  { key: 'neutral_history', title: 'Neutral Analyst', group: 'Risk', path: ['risk_debate', 'neutral_history'] },
  { key: 'final_trade_decision', title: 'Portfolio Manager', group: 'Decision', path: ['final_trade_decision'] },
];

/** Read a report section out of a completed run's `result_json`. */
export function readSection(result, section) {
  if (!result) return '';
  let node = result;
  for (const step of section.path) {
    if (node == null) return '';
    node = node[step];
  }
  return typeof node === 'string' ? node : '';
}

/** Report output languages — English plus the major Indian languages. */
export const OUTPUT_LANGUAGES = [
  'English',
  'Hindi',
  'Marathi',
  'Gujarati',
  'Bengali',
  'Tamil',
  'Telugu',
  'Kannada',
  'Malayalam',
  'Punjabi',
];

/** Data categories the run can route to a specific vendor. */
export const DATA_VENDOR_CATEGORIES = [
  { key: 'core_stock_apis', label: 'Core stock data' },
  { key: 'technical_indicators', label: 'Technical indicators' },
  { key: 'fundamental_data', label: 'Fundamental data' },
  { key: 'news_data', label: 'News data' },
];

export const DATA_VENDORS = ['yfinance', 'alpha_vantage'];

/** Providers whose thinking budget the `reasoning_effort` field maps onto. */
export const EFFORT_PROVIDERS = {
  openai: { label: 'Reasoning effort', options: ['low', 'medium', 'high'] },
  anthropic: { label: 'Effort', options: ['low', 'medium', 'high'] },
  google: { label: 'Thinking level', options: ['minimal', 'low', 'medium', 'high'] },
};
