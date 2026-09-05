# TradingAgents

A multi-agent LLM trading research platform. Specialised agents — analysts, researchers, a trader, and a risk committee — collaborate and debate their way to a position rating on a given ticker and date.

Ships with two front ends: an interactive terminal CLI, and a web app (FastAPI + React) with live run streaming and a browsable run history.

> **Research and educational use only.** Output is not financial, investment, or trading advice. Results vary with the backbone model, temperature, date range, data quality, and other non-deterministic factors. Do not trade real capital on this without your own due diligence.

---

## How it works

Analysis runs as a LangGraph state machine. Each analyst loops with its own tools until it has enough to write a report; the reports then feed a structured debate, and the debate feeds the final decision.

```
  Market ──► Sentiment ──► News ──► Fundamentals        (analyst team, tool loops)
                                          │
                                          ▼
                          Bull Researcher ⇄ Bear Researcher   (N rounds)
                                          │
                                          ▼
                                  Research Manager        (investment plan)
                                          │
                                          ▼
                                       Trader             (transaction proposal)
                                          │
                                          ▼
              Aggressive ──► Conservative ──► Neutral     (risk committee, N rounds)
                                          │
                                          ▼
                                 Portfolio Manager        (final rating)
```

### Analyst team

- **Market Analyst** — selects up to 8 complementary technical indicators (MACD, RSI, Bollinger, ATR, VWMA, moving averages) and reads trend, momentum, and volatility.
- **Sentiment Analyst** — aggregates news headlines, StockTwits cashtag messages (with user-labelled bullish/bearish tags), and Reddit discussion into a single sentiment read. Data is pre-fetched into the prompt rather than tool-called, so the model can't invent sources it doesn't have.
- **News Analyst** — macro and global headlines, insider transactions, and how events bear on market conditions.
- **Fundamentals Analyst** — balance sheet, cash flow, income statement, and company profile; intrinsic value and red flags.

### Researcher team

A bull and a bear researcher argue the analyst reports against each other for a configurable number of rounds, each responding directly to the other's last argument. The **Research Manager** then judges the debate and issues an investment plan with a five-tier rating.

### Trader

Turns the research plan into a concrete transaction proposal — direction, reasoning, and optional entry price, stop-loss, and position sizing.

### Risk committee and Portfolio Manager

Aggressive, conservative, and neutral risk analysts rotate through the proposal for a configurable number of rounds. The **Portfolio Manager** synthesises that debate into the final call: **Buy · Overweight · Hold · Underweight · Sell**, with an executive summary, investment thesis, and optional price target and time horizon.

The three decision-making agents (Research Manager, Trader, Portfolio Manager) use their provider's native structured-output mode, falling back to free-text generation automatically when a provider doesn't support it.

---

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS / Linux

pip install -r requirements.txt -r backend/requirements.txt
```

`requirements.txt` installs the core framework and its dependencies; `backend/requirements.txt` adds FastAPI, uvicorn, and SQLAlchemy for the web app. Install only the first if you just want the CLI or the Python package.

Requires Python 3.10+.

### API keys

Copy the example env file and fill in the provider you intend to use:

```bash
cp .env.example .env
```

```bash
OPENAI_API_KEY=...          # OpenAI (GPT)
GOOGLE_API_KEY=...          # Google (Gemini)
ANTHROPIC_API_KEY=...       # Anthropic (Claude)
XAI_API_KEY=...             # xAI (Grok)
DEEPSEEK_API_KEY=...        # DeepSeek
DASHSCOPE_API_KEY=...       # Qwen — International
DASHSCOPE_CN_API_KEY=...    # Qwen — China
ZHIPU_API_KEY=...           # GLM via Z.AI (international)
ZHIPU_CN_API_KEY=...        # GLM via BigModel (China)
MINIMAX_API_KEY=...         # MiniMax — Global
MINIMAX_CN_API_KEY=...      # MiniMax — China
SARVAM_API_KEY=...          # Sarvam AI (India)
OPENROUTER_API_KEY=...      # OpenRouter
ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage (optional data vendor)
```

Only the key for your chosen provider is required. For local models set `llm_provider: "ollama"` — the default endpoint is `http://localhost:11434/v1`, or point `OLLAMA_BASE_URL` at a remote `ollama serve`. Pull models with `ollama pull <name>` and pick "Custom model ID" in the CLI for anything not in the dropdown.

---

## Running the web app

Two processes. **Backend**, from the repository root:

```bash
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

**Frontend**, from `frontend/`:

```bash
npm install
npm run dev
```

The UI is then at `http://localhost:5173` and talks to the API on port 8000 (CORS for the Vite dev origin is already configured). Override with `VITE_API_BASE` and `VITE_WS_BASE` if you move either port.

Runs execute in a background thread and stream progress over a WebSocket at `/ws/runs/{run_id}`. History and results are stored in SQLite at `backend/tradingagents.db` — override with `TRADINGAGENTS_DB_PATH`.

Note: `--reload` restarts the server when you save a file, which kills any in-flight analysis. Drop it when running a full analysis, since those take several minutes.

### Pages

| Route | Purpose |
| --- | --- |
| `/` | Landing page |
| `/dashboard` | Run stats and recent activity |
| `/runs/new` | Configure and launch an analysis |
| `/runs/:id/live` | Live agent pipeline, log stream, and reports |
| `/runs/:id` | Full report for a completed run |
| `/history` | Searchable run history |
| `/config` | Runtime configuration editor |

---

## Running the CLI

```bash
tradingagents          # installed console script
python -m cli.main     # or run directly from source
```

You'll be prompted for ticker, analysis date, LLM provider, model tier, research depth, and output language. A live terminal dashboard then tracks each agent's status, tool calls, token usage, and reports as they complete. At the end you can save the full report to disk as per-section markdown files plus a combined `complete_report.md`.

```bash
tradingagents --checkpoint           # enable checkpoint resume for this run
tradingagents --clear-checkpoints    # reset all checkpoints before running
```

---

## Python usage

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

final_state, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

Adjust the config to change provider, models, or debate depth:

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"           # openai, google, anthropic, xai, deepseek,
                                            # qwen, qwen-cn, glm, glm-cn, minimax,
                                            # minimax-cn, sarvam, openrouter, ollama
config["deep_think_llm"] = "gpt-5.4"        # complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini"  # fast tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

You can also select a subset of analysts:

```python
ta = TradingAgentsGraph(selected_analysts=["market", "fundamentals"], config=config)
```

### Configuration

All options live in `tradingagents/default_config.py`. Any of these can be set via environment variable without editing code — values are coerced to the type of the existing default:

| Variable | Sets |
| --- | --- |
| `TRADINGAGENTS_LLM_PROVIDER` | LLM provider |
| `TRADINGAGENTS_DEEP_THINK_LLM` | Deep-thinking model |
| `TRADINGAGENTS_QUICK_THINK_LLM` | Quick-thinking model |
| `TRADINGAGENTS_LLM_BACKEND_URL` | Custom API endpoint |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | Report language |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | Bull/bear rounds |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | Risk committee rounds |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | Checkpoint resume |
| `TRADINGAGENTS_BENCHMARK_TICKER` | Alpha benchmark override |
| `TRADINGAGENTS_RESULTS_DIR` · `TRADINGAGENTS_CACHE_DIR` · `TRADINGAGENTS_MEMORY_LOG_PATH` | Storage paths |

### Data vendors

Each data category routes to a configurable vendor, with automatic fallback if one hits a rate limit:

```python
config["data_vendors"] = {
    "core_stock_apis":     "yfinance",       # or alpha_vantage
    "technical_indicators": "yfinance",
    "fundamental_data":     "yfinance",
    "news_data":            "yfinance",
}
```

---

## Persistence and recovery

### Decision log

Always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md` as a pending entry. On the next run for the same ticker, the realised return is fetched (raw, plus alpha against a benchmark), a short reflection is generated, and the most recent same-ticker decisions plus recent cross-ticker lessons are injected into the Portfolio Manager's prompt — so each analysis carries forward what worked and what didn't.

The alpha benchmark is chosen from the ticker's exchange suffix — `^NSEI` for `.NS`, `^N225` for `.T`, `^FTSE` for `.L`, SPY for US listings, and so on. Override globally with `TRADINGAGENTS_BENCHMARK_TICKER`.

### Checkpoint resume

Opt-in via `--checkpoint`. LangGraph saves state after each node, so an interrupted run resumes from the last successful step instead of starting over. You'll see `Resuming from step N` in the logs on a resume, or `Starting fresh` otherwise. Checkpoints clear automatically on success.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db`.

---

## Project layout

```
tradingagents/          Core framework
  agents/               Agent definitions, prompts, tools, schemas
  dataflows/            Data vendors (yfinance, Alpha Vantage, Reddit, StockTwits)
  graph/                LangGraph setup, routing, propagation, reflection
  llm_clients/          Provider clients, model catalog, capability table
cli/                    Interactive terminal application
backend/                FastAPI server — REST + WebSocket
frontend/               React + Vite web UI
tests/                  Test suite
```

## Tests

```bash
pip install pytest
pytest
```
