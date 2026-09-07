# Deploying MarketMinds

This guide deploys the app the way it is designed to be deployed publicly:

- **one container** — the API serves the compiled UI, so there is no separate
  frontend host, no second domain and no CORS to configure;
- **managed PostgreSQL** — the container's disk does not survive a restart on
  any free tier, so run history lives in a database that does;
- **bring-your-own API keys** — visitors supply their own LLM credential in the
  browser, so you are not paying for other people's analyses.

Everything below fits inside free tiers. Costs are noted where a tier ends.

---

## Before you start

Read this part; it decides whether you should deploy at all.

**Sign-in is required to start a run, and nothing else.** Anyone can read the
landing page, the guide, and whichever run you publish as a demo. Starting an
analysis needs a Google account, and each user's runs are private to them.

**Auth is opt-in, and forgetting it fails open.** With `SUPABASE_URL` unset the
instance accepts unauthenticated runs and shows every stored run to everyone —
correct for a local checkout, wrong for a public URL. The server logs a warning
at startup when it is in that state; on a deployment, treat that line as a bug.

**Runs are slow and stateful.** A full analysis takes several minutes and holds
a background thread the whole time. Free tiers that sleep idle instances will
kill a run in flight. Pick a host that does not sleep, or accept that runs
started just before an idle timeout will not finish.

**Nothing here is investment advice** and the deployed app should say so. It
already does, on every report.

---

## Step 1 — Push the repository

Any of the hosts below deploy from a Git repository. GitHub is the path of
least resistance.

```bash
git remote add origin https://github.com/<you>/marketminds.git
git push -u origin main
```

Confirm `.env` is **not** in the push. It is already in `.gitignore`; check
anyway, because a leaked provider key is the one mistake here that costs real
money:

```bash
git ls-files | grep -x ".env"    # must print nothing
```

And confirm the frontend is actually complete in the commit. `.gitignore`
carried a bare `lib/` from the Python template, which also matched
`frontend/src/lib/` and kept that whole directory out of every commit — a
clone would fail at `npm run build` with unresolved imports. The rule is now
anchored to the repo root, but check before you trust a deploy:

```bash
git ls-files frontend/src/lib | wc -l    # must be 7, not 0
```

---

## Step 2 — Create the Supabase project

Supabase gives you both halves of what this needs — a PostgreSQL database and
Google sign-in — on one free tier.

1. **New project.** Pick a region near your users; for Indian traffic that is
   `ap-south-1` (Mumbai). Note the **project ref** from the URL — it looks like
   `abcdefghijklmnopqrst` and appears throughout this guide as
   `your-project-ref`.
2. **Save the database password** it shows you at creation. It is displayed
   once; if you miss it, reset it under Project Settings → Database.
3. **Copy the publishable key** from Project Settings → API. It looks like
   `sb_publishable_...`. This one is not a secret — it is designed to ship
   inside a frontend bundle.

### Create the tables

The app creates its own schema on first startup, so the simplest path is to set
`DATABASE_URL` and start the container once. To do it ahead of time, run
`scripts/migrate_to_postgres.py` (below) — it creates anything missing.

### Lock the tables against PostgREST

**Do not skip this.** Supabase publishes every table in the `public` schema
through PostgREST, reachable with the publishable key that ships in your
frontend bundle. Without this step, `GET /rest/v1/runs` with that key returns
every user's analyses. Run it in the SQL editor:

```sql
ALTER TABLE runs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_configs  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON runs, run_events, memory_entries, saved_configs
  FROM anon, authenticated;
```

RLS with **no policies** is deny-by-default. See
[Why the tables are locked](#why-the-tables-are-locked) for why this is not
what separates one user's runs from another's.

### Get the connection string

Project Settings → Database → Connection string → URI. Choose **Session
pooler**, not Direct connection and not Transaction pooler:

| Method | Use it? | Why |
|---|---|---|
| Direct | no | IPv6-only; most free-tier hosts are IPv4-only |
| Transaction pooler | no | No prepared statements — psycopg 3 prepares automatically and the app breaks with `prepared statement already exists` |
| **Session pooler** | **yes** | IPv4, full session semantics, works unchanged |

```
postgresql://postgres.your-project-ref:PASSWORD@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Percent-encode the password if it contains `@ : / ? # [ ] %`.

### Bring existing history across (optional)

If you have been running locally, this is what stops the deployed dashboard
being empty:

```bash
# Put DATABASE_URL in .env, then:
python scripts/migrate_to_postgres.py --source backend/marketminds.db --dry-run
python scripts/migrate_to_postgres.py --source backend/marketminds.db --user-id <your-id>
```

It copies runs, their event logs, and both forms of the decision log. Re-running
skips what is already there, so an interrupted migration can be restarted.

Find `<your-id>` after signing in once: Supabase → Authentication → Users, or
`SELECT id, email FROM auth.users;`. Without it the rows have no owner and stay
invisible to every signed-in user. To claim them afterwards:

```sql
UPDATE runs           SET user_id = '<your-id>' WHERE user_id IS NULL;
UPDATE memory_entries SET user_id = '<your-id>' WHERE user_id IS NULL;

-- Publish runs into the signed-out showcase
UPDATE runs SET is_public = 1 WHERE status = 'completed';
```

---

## Step 2b — Turn on Google sign-in

This is the one part nobody can do for you: it needs your Google Cloud
account.

**In Google Cloud Console** (console.cloud.google.com):

1. Create or pick a project, then **APIs & Services → OAuth consent screen**.
   External, fill in the app name and your support email, save.
2. **Credentials → Create credentials → OAuth client ID → Web application**.
3. Under **Authorised redirect URIs**, add exactly:

   ```
   https://your-project-ref.supabase.co/auth/v1/callback
   ```

4. Copy the **Client ID** and **Client secret**.

**In Supabase** (Authentication → Sign In / Providers → Google):

5. Enable Google, paste the Client ID and Client secret, save.
6. Under **Authentication → URL Configuration**, set **Site URL** to your
   deployed URL (e.g. `https://marketminds.onrender.com`) and add it to
   **Redirect URLs**. Add `http://localhost:5173` too if you want sign-in to
   work in local development.

That last step is the one people miss. Without the Site URL, Google returns
the user to `localhost` after a successful sign-in on your live site.

---

## Step 3 — Deploy the container

### Render (recommended)

Render builds the `Dockerfile` directly and its free web service does not
sleep mid-request the way a scale-to-zero platform does.

1. **New → Web Service**, connect the repository.
2. Runtime: **Docker**. Render finds the `Dockerfile` at the root.
3. Instance type: Free (512 MB). Upgrade to Starter ($7/mo) if runs get
   OOM-killed — several agents plus yfinance in one process is not tiny.
4. Add a **Disk**: mount path `/data`, 1 GB. This is still needed with
   Postgres — see [What still lives on disk](#what-still-lives-on-disk).
5. Environment variables — see [the table below](#environment-variables).
6. Deploy.

Render sets `PORT` itself and the container already honours it.

### Railway

1. **New Project → Deploy from GitHub repo**. Railway detects the Dockerfile.
2. Add a volume mounted at `/data`.
3. Set the environment variables.
4. Generate a domain under Settings → Networking.

Railway's free allowance is credit-based rather than time-based; a low-traffic
deployment fits, a busy one will not.

### Fly.io

```bash
fly launch --no-deploy          # accept the detected Dockerfile
fly volumes create data --size 1
```

Then in `fly.toml`, mount it and stop the machine from suspending mid-run:

```toml
[[mounts]]
  source      = "data"
  destination = "/data"

[http_service]
  internal_port        = 8000
  auto_stop_machines   = false     # a suspended machine loses the run
  min_machines_running = 1
```

```bash
fly secrets set DATABASE_URL="postgresql://..."
fly deploy
```

---

## Environment variables

| Variable | Required | Value |
|---|---|---|
| `DATABASE_URL` | **yes** | The DSN from step 2 |
| `SUPABASE_URL` | **yes** | `https://your-project-ref.supabase.co` |
| `SUPABASE_ANON_KEY` | **yes** | Your publishable key, `sb_publishable_...` |
| `PORT` | host-set | Render/Railway/Fly set this; the container reads it |
| `FRONTEND_URL` | no | Only if you serve the UI from a different origin |
| `GOOGLE_API_KEY` *(or another provider)* | no | A server-side fallback key |
| `MARKETMINDS_MAX_DEBATE_ROUNDS` | no | `1` keeps runs short and cheap |

The two Supabase values are marked required because without them the instance
runs **open** — see [Before you start](#before-you-start). Neither is a secret;
the frontend fetches both from `/api/auth/config` and uses them in the browser.

Set nothing else. The Docker image already points the database path, cache and
memory log at `/data`.

### Should you set a provider key at all?

Two ways to run this publicly:

**No server key.** Every visitor must paste their own key before a run starts,
and the preflight check rejects a bad one with a clear message. You spend
nothing and hold no credential. This is the honest default for a public link.

**A server key as fallback.** Visitors without a key use yours. Convenient for
a demo you are walking someone through — and a bill waiting to happen on a
public URL, because there is no auth and no rate limit. If you do this, use a
key with a hard spend cap set at the provider, not at the app.

A visitor's own key always takes precedence over the server's.

---

## Why the tables are locked

Supabase publishes every table in the `public` schema through PostgREST, and
the publishable key that reaches it is in the frontend bundle where anyone can
read it. Left alone, `GET /rest/v1/runs` with that key would return every
user's analyses.

So all four tables have **row-level security enabled with no policies** — the
deny-by-default state — and the `anon` and `authenticated` roles have had their
grants revoked. Both were verified after provisioning: each table answers `401`
to the publishable key.

RLS is not what separates one user's runs from another's. The backend connects
as the database owner, which bypasses RLS entirely; ownership is enforced in
the FastAPI routers and tested in `tests/test_auth_scoping.py`. RLS here does
one job: keeping the tables unreachable except through the application.

If you ever add a policy to these tables, you are opening that door. Do it
deliberately.

---

## What still lives on disk

Postgres now holds runs, reports, events, usage counters **and the decision
log**. Two things are still files, and are the reason for the `/data` volume:

- **the market data cache** (`/data/cache`) — regenerable, but a cold cache
  makes the first run of the day noticeably slower;
- **checkpoints** (`/data/cache/checkpoints`) — only when checkpointing is
  enabled, which it is not by default.

Both are disposable. Deploy without a volume and the app is fully functional;
the first run after each restart is just slower. That is a change from the
earlier setup: the decision log used to live here, and losing it actually made
later analyses worse. It is now a database table, so a restart costs nothing
that matters.

---

## Verifying the deployment

```bash
curl https://<your-app>/api/health        # {"status":"ok"}
curl https://<your-app>/api/auth/config   # {"enabled":true,...} — NOT false
curl https://<your-app>/api/runs          # only runs you published
```

`"enabled": false` on the second call is the important failure: it means the
Supabase variables did not reach the process, and the instance is running open.

Then open the URL and check, in this order:

- **signed out** — the dashboard shows a selection of your published runs and a
  "sign in" banner, and `/guide` is readable. Nothing appears until at least one
  run has `is_public = 1`;
- **sign in with Google** — you land back on the same page, not on localhost.
  If you land on localhost, the Site URL in Supabase is wrong;
- **your history appears** and the demo run disappears from it (it belongs to
  the signed-out view, not to you);
- **add a provider key and run one ticker** — the event log should stream agent
  output live, which proves the WebSocket survived your host's proxy *and*
  that its token was accepted;
- **download the PDF** — ₹ should render as a rupee sign, not a black box.

If history is empty after a restart, `DATABASE_URL` did not reach the process.
Check it in the host's dashboard rather than in the repo.

---

## Upgrading a running deployment

Push to `main`; every host above rebuilds on push. The startup migration adds
any new columns to the existing database automatically.

This handles **additions only**. A column rename, type change or drop needs
Alembic, which this project does not carry — if the schema ever changes that
way, you will need to add it or migrate by hand. Saying so plainly here is
better than discovering it during a deploy.

---

## Cost, honestly

| | Free tier | When it ends |
|---|---|---|
| Render web service | 512 MB, always-on | OOM under load → $7/mo Starter |
| Neon / Supabase | 0.5 GB | Thousands of runs before it matters |
| LLM usage | — | Paid by whoever supplies the key |

With BYO keys and no server key, a low-traffic deployment costs nothing.
