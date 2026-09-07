# MarketMinds

A multi-agent LLM research platform for **Indian equities**. Specialised agents —
analysts, researchers, a trader, and a risk committee — collaborate and debate their
way to a position rating on an NSE or BSE listing.

Built for one market on purpose: tickers resolve against NSE first and BSE second,
alpha is measured against the Nifty 50 or the Sensex, dates are validated against the
NSE trading calendar, prices are stated in rupees, and the news layer reads Indian
media and RBI/SEBI policy rather than the Fed and the S&P 500.

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
- **Sentiment Analyst** — reads company coverage from Indian media alongside the front pages of the domestic financial press, and separates the company's own story from the market-wide mood. Data is pre-fetched into the prompt rather than tool-called, so the model can't invent sources it doesn't have, and the prompt states outright that no retail or social data was collected so the report cannot imply one.
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

## Data sources

Every source below is free and needs no API key. Each degrades to a clearly
labelled gap rather than an exception, so one dead feed never fails a run.

| Category | Source | Notes |
| --- | --- | --- |
| Price, indicators, fundamentals | Yahoo Finance | NSE (`.NS`) and BSE (`.BO`) listings |
| Company news | Google News (India edition) | Searched by company name *and* symbol, then filtered to items that actually mention the company |
| Indian financial press | Economic Times (markets, stocks, economy), Moneycontrol (business, markets, results), Livemint (markets, companies), Business Standard, Hindu BusinessLine | RSS, merged and deduplicated by headline |
| Macro and policy | Google News, across 12 themes | RBI policy and liquidity · SEBI and regulation · government policy and the Budget · CPI/WPI inflation · GDP, IIP and core sector · GST and direct tax · FII/DII flows · rupee, forex and gold reserves · MSCI and FTSE index rejigs · global spillovers via crude and US rates · IPO activity · mutual-fund flows |
| Sector news | Google News, across 12 sectors | IT · banking · financial services and fintech · pharma · auto and EV · FMCG · metals · energy · realty · infrastructure · healthcare · new-age tech |
| Market context | Yahoo Finance | Nifty 50, Sensex, Bank Nifty, Nifty Next 50, Midcap 50, Nifty 500; India VIX; ten sector indices; USD/INR, Brent, gold, US 10-year yield, dollar index — each with 1D, 1W and 1M moves |
| Exchange filings | NSE corporate announcements | Undocumented endpoint; blocks many datacentre IPs, so treated as best-effort |

**Not used, and why:** StockTwits indexes US cashtags and returns HTTP 404 for every
NSE symbol. Reddit blocks all unauthenticated API traffic, and its RSS endpoints
rate-limit too aggressively to stand in — a sweep paced at four seconds still returned
HTTP 429 on four of five subreddits. NDTV Profit and Zeebiz reject non-browser clients.
Financial Express serves HTML rather than RSS at its feed URL. YouTube channel feeds
carry titles only, with no transcript, and hardcoded channel ids rot silently.

There is therefore **no retail or social sentiment source**. The Sentiment Analyst
produces a media sentiment read and its prompt forbids describing retail positioning
or a bullish/bearish ratio, so a limitation of the data never turns into a fabricated
signal downstream.

### Ticker format

A bare name resolves to NSE, so `RELIANCE` becomes `RELIANCE.NS`; if NSE has no data
the resolver retries BSE. Resolution is verified against real price data before a run
starts, so a typo fails immediately rather than producing an empty report several
minutes later. An explicit suffix is respected. Symbols from other markets
(`7203.T`, `0700.HK`, `AAPL`) are rejected by name.

BSE scrip codes are not supported — the price source keys BSE listings by symbol
(`RELIANCE.BO`), not by code.

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

Only the key for your chosen provider is required.

For local models set `llm_provider: "ollama"` — the default endpoint is `http://localhost:11434/v1`, or point `OLLAMA_BASE_URL` at a remote `ollama serve`. Pull models with `ollama pull <name>` and pick "Custom model ID" in the CLI for anything not in the dropdown.

---

## Reports and API keys

### PDF export

A finished run downloads as a single PDF — cover page with the rating, run
metadata and usage, then every agent's report in pipeline order. Rendered
server-side with ReportLab, so it needs no browser and works unchanged inside
the container.

The agents still exchange **markdown** between themselves, and the decision log
stays markdown because it is injected into the Portfolio Manager's prompt.
Only what a person downloads is a PDF.

One wrinkle worth knowing: ReportLab's built-in fonts predate the rupee sign
(U+20B9, introduced 2010), so every `₹` would render as a black box. The image
installs `fonts-dejavu-core` and the renderer picks the first font it finds
that carries the glyph, falling back to writing "Rs." rather than printing
squares.

### Bring your own API key

Visitors can supply their own provider credential from the New analysis page,
which is what makes a public deployment practical — the host holds no keys and
spends nobody's quota.

The key is:

- kept in **that browser's** `localStorage`, never on the server;
- sent with the run request that needs it and used for that run only;
- **never** written to the database, the run's `config_snapshot`, the API
  response, or any log — the field is declared `exclude=True` and the snapshot
  is built from an explicit allowlist;
- never placed in the preflight cache, since an `lru_cache` retains its
  arguments for the life of the process.

`tests/test_byo_api_key.py` pins each of those properties. If the server also
has a key configured for that provider, the visitor's key takes precedence and
the server key is the fallback.

### Google sign-in

Optional, and off unless configured. Set `SUPABASE_URL` and
`SUPABASE_ANON_KEY` and the app requires a signed-in Google account before an
analysis can start — and nowhere else. The landing page, the guide, the
dashboard and any run published as a demo stay readable signed out.

With auth on:

- a run belongs to whoever started it, and another user asking for it gets a
  404 rather than a 403, so an id's existence is not confirmed;
- `is_public = 1` publishes a run into the signed-out showcase. Visitors see a
  selection of published runs ordered by a random seed their browser generates
  once, so different people land on different examples while each sees a stable
  set across reloads. Only published runs ever appear there — never the table
  at large;
- the decision log is **shared for reading and private for display** — every
  run learns from the whole pool, while the Memory page shows a user only their
  own entries. Worth being clear about: another user's reasoning can influence
  your report, because it fed the prompt. The history is private, its
  influence is not;
- the live WebSocket carries the session token as a subprotocol rather than a
  query parameter, which keeps a live credential out of proxy access logs.

With those variables unset the instance runs open — right for a local checkout,
wrong for a public URL — and says so in a startup warning. The rules are pinned
in `tests/test_auth_scoping.py`.

Supabase Auth is used only as an identity provider. The backend connects to
Postgres directly and enforces ownership in its routers; row-level security is
enabled with no policies purely to keep the tables unreachable through
PostgREST, whose publishable key ships in the frontend bundle.

---

## Running with Docker

One image, one container, one port — the React app is compiled at build time
and served by the same FastAPI process that answers `/api` and `/ws`.

```bash
cp .env.example .env        # add the API key for your provider
docker compose up --build
```

The app is then at **http://localhost:8000**.

Or without Compose:

```bash
docker build -t marketminds .
docker run -p 8000:8000 --env-file .env -v marketminds-data:/data marketminds
```

### What persists

Everything mutable lives under `/data`, so one volume carries the whole state:

| Path | Contents |
| --- | --- |
| `/data/marketminds.db` | Run history, reports, events, usage counters |
| `/data/memory/` | The decision log the agents learn from |
| `/data/cache/` | Cached market data and checkpoint databases |
| `/data/logs/` | Saved run results |

Drop the volume and the system forgets its past calls — the Memory page starts
empty and the Portfolio Manager loses its prior lessons.

### Deploying it publicly

[DEPLOYMENT.md](DEPLOYMENT.md) covers putting this on a free-tier host with a
managed PostgreSQL database: which host, which database, which environment
variables, what still needs a disk, and what it costs once the free tier runs
out. Read its opening section first — a deployed instance has **no
authentication**, so every visitor sees every run.

### Bringing existing history into the container

The container keeps its state in a Docker volume, not in your working copy, so
a fresh container starts with an empty dashboard even if you have run analyses
locally. The two stores are separate files:

| | Running locally | Running in Docker |
| --- | --- | --- |
| Database | `backend/marketminds.db` | `/data/marketminds.db` in the volume |
| Decision log | `~/.marketminds/memory/` | `/data/memory/` in the volume |

To carry your existing runs over, copy both in and **fix their ownership** —
`docker cp` writes files as root, while the app runs as uid 10001, which leaves
the history readable but every new run failing with *"attempt to write a
readonly database"*:

```bash
docker compose up -d

docker cp backend/marketminds.db marketminds:/data/marketminds.db
docker cp ~/.marketminds/memory/trading_memory.md marketminds:/data/memory/trading_memory.md

# Required — without this the app can read the history but not write to it.
docker exec -u 0 marketminds chown -R marketminds:marketminds /data

docker compose restart
```

On Windows, run these from PowerShell or prefix with `MSYS_NO_PATHCONV=1` in Git
Bash, which otherwise rewrites `/data` into a Windows path.

Going the other way — copying the container's data back out:

```bash
docker cp marketminds:/data/marketminds.db backend/marketminds.db
```

Note that only one of the two can run at a time: both bind host port 8000, so
start the container only after stopping a local `uvicorn` (or publish it
elsewhere with `MARKETMINDS_PORT`).

### Configuration

API keys are read from the environment at run time and are never baked into the
image. Any variable from `.env.example` works, as does every `MARKETMINDS_*`
override:

```bash
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=... \
  -e MARKETMINDS_LLM_PROVIDER=google \
  -e MARKETMINDS_MAX_DEBATE_ROUNDS=2 \
  -v marketminds-data:/data marketminds
```

Set `PORT` to listen on something other than 8000 inside the container, or
`MARKETMINDS_PORT` to change the host port that Compose publishes.

To reach a provider running on the host — Ollama, say — point it at the host
gateway rather than `localhost`, which inside a container means the container
itself:

```bash
docker run -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434/v1 \
  --add-host=host.docker.internal:host-gateway \
  -v marketminds-data:/data marketminds
```

### The CLI, from the same image

```bash
docker run -it --rm --env-file .env -v marketminds-data:/data marketminds marketminds
```

### Notes

- An analysis runs for several minutes in a background thread. `stop_grace_period`
  is set to 60s so a `docker compose stop` does not sever one after 10 seconds.
- The container runs as an unprivileged user (uid 10001). If you bind-mount a
  host directory over `/data` instead of using a named volume, make sure that
  directory is writable by it.
- There is no `--reload`: it would restart the server on file changes and kill
  any in-flight analysis.

---

## Running the web app

For a single-command setup, see [Running with Docker](#running-with-docker)
above. To run the two processes directly instead — **Backend**, from the
repository root:

```bash
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

**Frontend** (React + Vite + Tailwind CSS v4), from `frontend/`:

```bash
npm install
npm run dev
```

The UI is then at `http://localhost:5173`. It calls the API on its own origin
and Vite proxies `/api` and `/ws` through to port 8000, so no CORS setup or
hardcoded port is involved. Point `VITE_DEV_API_TARGET` elsewhere if the backend
does not run on 8000, or set `VITE_API_BASE` / `VITE_WS_BASE` when the frontend
is deployed on a different origin from the API.

Runs execute in a background thread. Progress streams over a WebSocket at
`/ws/runs/{run_id}`: agent start/finish transitions, every tool call with its
arguments, each report section the moment its agent writes it, and live token
counters. Agent status is inferred from the graph state after each node, so
reopening a run mid-flight restores the real pipeline position rather than
starting the view from scratch.

History, results and usage counters are stored in **SQLite** at
`backend/marketminds.db` — override the path with `MARKETMINDS_DB_PATH`. New
columns on an existing database are added automatically at startup.

Set **`DATABASE_URL`** to a PostgreSQL DSN to switch engines; everything above
the ORM is unchanged. JSON columns become `JSONB` automatically, and the DSN
schemes managed providers hand out (`postgres://`, `postgresql://`) are
normalised to the psycopg 3 driver the image ships, so a pasted connection
string works as-is.

```bash
# same engine locally as in production
docker compose -f docker-compose.postgres.yml up -d --build
```

A deployed instance also keeps the **decision log** in the database rather than
in `trading_memory.md`, and stops writing duplicate state-log files — the CLI
keeps using the markdown log. `scripts/migrate_to_postgres.py` moves existing
runs, events and log entries across, and is safe to re-run.

Use Postgres when the container's disk is ephemeral, or when more than one
process needs the data — SQLite takes a write lock on the whole file and cannot
be shared. The startup migration handles **added** columns on both engines;
a rename, type change or drop needs Alembic, which this project does not yet
carry.

Note: `--reload` restarts the server when you save a file, which kills any
in-flight analysis. Drop it when running a full analysis, since those take
several minutes.

### Pages

| Route | Purpose |
| --- | --- |
| `/` | Landing page |
| `/guide` | How to use the site — the workflow, all five pipeline stages, FAQ |
| `/dashboard` | Run stats, rating mix, activity and token usage |
| `/runs/new` | Configure and launch an analysis, with an advanced panel |
| `/runs/:id/live` | Live agent pipeline, streaming reports, event log, stop control |
| `/runs/:id` | Full report, timeline and configuration for a finished run |
| `/history` | Searchable, paginated run history with export and delete |
| `/memory` | Decision log — past calls, realised return, alpha and reflections |
| `/config` | Runtime configuration, saved presets, and provider key status |

### API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/runs` | Create and start a run |
| `GET` | `/api/runs` | List runs (`ticker`, `status`, `limit`, `offset`, `seed`) |
| `GET` | `/api/runs/stats` | Aggregate counters, rating mix, activity, usage (`seed`) |
| `GET` | `/api/runs/{id}` | Full run detail with its event history |
| `POST` | `/api/runs/{id}/cancel` | Stop an in-flight run at the next agent boundary |
| `DELETE` | `/api/runs/{id}` | Delete a finished run and its events |
| `GET` | `/api/runs/{id}/export` | Download the run as a PDF report |
| `GET` | `/api/auth/config` | Whether sign-in is available, and its client config |
| `GET` | `/api/auth/me` | The caller's identity, or null |
| `GET` · `PUT` | `/api/config` | Read / update the in-memory runtime config |
| `GET` · `POST` · `DELETE` | `/api/config/saved` | Named config presets |
| `GET` | `/api/providers` | Providers, their key env var, and whether it is set |
| `GET` | `/api/providers/{name}/models` | Quick and deep model catalog |
| `GET` | `/api/memory` | Decision log entries, returns, alpha and reflections |
| `WS` | `/ws/runs/{id}` | Live run event stream |

Cancellation is cooperative: the flag is checked between graph nodes, so the
agent currently waiting on its provider finishes that call before the run
unwinds. Reports written before the stop are kept.

---

## Running the CLI

```bash
marketminds          # installed console script
python -m cli.main     # or run directly from source
```

You'll be prompted for ticker, analysis date, LLM provider, model tier, research depth, and output language. A live terminal dashboard then tracks each agent's status, tool calls, token usage, and reports as they complete. At the end you can save the full report to disk as per-section markdown files plus a combined `complete_report.md`.

```bash
marketminds --checkpoint           # enable checkpoint resume for this run
marketminds --clear-checkpoints    # reset all checkpoints before running
```

---

## Python usage

```python
from marketminds.graph.trading_graph import MarketMindsGraph
from marketminds.default_config import DEFAULT_CONFIG

ta = MarketMindsGraph(debug=True, config=DEFAULT_CONFIG.copy())

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

ta = MarketMindsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

You can also select a subset of analysts:

```python
ta = MarketMindsGraph(selected_analysts=["market", "fundamentals"], config=config)
```

### Configuration

All options live in `marketminds/default_config.py`. Any of these can be set via environment variable without editing code — values are coerced to the type of the existing default:

| Variable | Sets |
| --- | --- |
| `MARKETMINDS_LLM_PROVIDER` | LLM provider |
| `MARKETMINDS_DEEP_THINK_LLM` | Deep-thinking model |
| `MARKETMINDS_QUICK_THINK_LLM` | Quick-thinking model |
| `MARKETMINDS_LLM_BACKEND_URL` | Custom API endpoint |
| `MARKETMINDS_OUTPUT_LANGUAGE` | Report language |
| `MARKETMINDS_MAX_DEBATE_ROUNDS` | Bull/bear rounds |
| `MARKETMINDS_MAX_RISK_ROUNDS` | Risk committee rounds |
| `MARKETMINDS_CHECKPOINT_ENABLED` | Checkpoint resume |
| `MARKETMINDS_BENCHMARK_TICKER` | Alpha benchmark override |
| `MARKETMINDS_REQUIRE_TRADING_DAY` | Reject an analysis date the NSE was closed |
| `MARKETMINDS_RESULTS_DIR` · `MARKETMINDS_CACHE_DIR` · `MARKETMINDS_MEMORY_LOG_PATH` | Storage paths |

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

Always on. Each completed run records its decision as a pending entry — in
`~/.marketminds/memory/trading_memory.md` for the CLI and local runs, or in the
`memory_entries` table when the web app is running against a database. On the next run for the same ticker, the realised return is fetched (raw, plus alpha against a benchmark), a short reflection is generated, and the most recent same-ticker decisions plus recent cross-ticker lessons are injected into the Portfolio Manager's prompt — so each analysis carries forward what worked and what didn't.

The alpha benchmark follows the exchange: the **Nifty 50** (`^NSEI`) for `.NS`
listings and the **Sensex** (`^BSESN`) for `.BO`. Override globally with
`MARKETMINDS_BENCHMARK_TICKER` — useful for measuring a bank against `^NSEBANK`
rather than the broad index.

### Checkpoint resume

Opt-in via `--checkpoint`. LangGraph saves state after each node, so an interrupted run resumes from the last successful step instead of starting over. You'll see `Resuming from step N` in the logs on a resume, or `Starting fresh` otherwise. Checkpoints clear automatically on success.

Per-ticker SQLite databases live at `~/.marketminds/cache/checkpoints/<TICKER>.db`.

---

## Project layout

```
marketminds/          Core framework
  agents/               Agent definitions, prompts, tools, schemas
  dataflows/            Data sources
    india.py              Exchanges, ticker resolution, indices, NSE calendar, INR
    india_news.py         Google News India + domestic outlet RSS aggregation
    india_market.py       Index, sector, currency and commodity snapshot
    nse.py                NSE corporate announcements (best-effort)
  graph/                LangGraph setup, routing, propagation, reflection
  llm_clients/          Provider clients, model catalog, capability table,
                          preflight model validation
  reporting/            PDF rendering for downloaded reports
scripts/
  migrate_to_postgres.py  One-shot SQLite -> Postgres history migration
cli/                    Interactive terminal application
backend/                FastAPI server — REST + WebSocket, serves the built UI
frontend/               React + Vite + Tailwind web UI
tests/                  Test suite
Dockerfile              Single-image build: UI compiled, then served by the API
docker-compose.yml      One service, one port, one data volume (SQLite)
docker-compose.postgres.yml   App plus PostgreSQL, deployment-shaped
```

## Tests

```bash
pip install pytest
pytest
```
