# Deployment — ForexAI on Render (free tier)

Host the signal generator and dashboard so anyone with a login can use them,
while MT5 order execution stays on your own PC.

```
Browser (any user with an account)
   │  HTTPS
   ▼
forexai-dashboard.onrender.com      static SPA + nginx (proxies /api)
   │
   ▼
forexai-csharp-api.onrender.com     JWT auth, signal history, audit trail
   │  X-API-Key
   ▼
forexai-python-ai.onrender.com      LangGraph signal generator
   │
   ▼
Neon (free Postgres)                users, signals, RAG evidence

your PC:  MT5 terminal + run_signal_bridge.py
   ▲        webhook POST, pushed by the hosted service
   │  cloudflared quick tunnel (free HTTPS, no account)
   └── https://<random>.trycloudflare.com/signal?token=<BRIDGE_TOKEN>
```

**Total cost: $0.** Render (3 free web services), Neon, GitHub Actions,
UptimeRobot and cloudflared are all card-free. You only pay for the API keys
you already use.

> **Why there is no cron service.** Render cron jobs have no free tier —
> `plan: free` is rejected with *"free not a valid plan for service type
> cron"*, and every cron service carries a **minimum monthly charge**.
> Database migrations therefore run from
> `.github/workflows/db-migrate.yml`, which is free and can be triggered by
> hand from the Actions tab.

---

## 0. Before you start

Push the work to GitHub — Render builds from the repository:

```powershell
git add -A
git commit -m "MT5 phases 1-4, signal bridge, Render deployment"
git push origin main
```

Create these free accounts: [Render](https://render.com),
[Neon](https://neon.tech), [UptimeRobot](https://uptimerobot.com).

Generate the secrets you need and keep them in a password manager:

| Secret | How |
| --- | --- |
| `AI_SERVICE_API_KEY` | Render generates it (`generateValue: true`) |
| `PythonApi__ApiKey` | **Copy** the generated `AI_SERVICE_API_KEY` |
| `Jwt__Key` | Render generates it (≥32 bytes) |
| `BRIDGE_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Neon connection string | Neon dashboard → Connection details |

---

## 1. Publish the quant model artifacts (do this first)

`forexai-ai/models/*.joblib` is **git-ignored** (48 MB of trained models), so
a hosted build clones an empty `models/` directory. The Dockerfile therefore
fetches the artifacts from a release, verifying SHA-256:

1. Create a GitHub release on this repo, tag **`models-v1`**.
2. Upload as release assets:
   - `random_forest_full.joblib`
   - `xgboost_full.joblib`
   - `logistic_regression_full.joblib`
   - `calibration.json`

   (from your local `forexai-ai/models/`)
3. Confirm the checksums still match `forexai-ai/models/ARTIFACTS.sha256`:

```powershell
cd forexai-ai
python scripts/fetch_model_artifacts.py --check
```

Retraining means regenerating that manifest and re-uploading:

```powershell
cd forexai-ai/models
Get-ChildItem *_full.joblib, calibration.json | ForEach-Object {
  '{0}  {1}' -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name
}
```

> ⚠️ **This step is mandatory before the first deploy.** A hosted build clones
> the repository without the `.joblib` files, so it downloads them from the
> release. Until the release exists the build **fails** on purpose, with an
> explicit `HTTP 404 ... Upload the artifacts to the release named by
> MODEL_ARTIFACTS_BASE_URL` message. That is deliberate: shipping a signal
> generator whose quant ensemble silently vanished would be worse than a
> failed deploy.
>
> In the build log you want to see `Verified random_forest_full.joblib`,
> `Verified xgboost_full.joblib` and `Verified logistic_regression_full.joblib`.



---

## 2. Create the Neon database

1. Neon → **Create project** → name `forexai` → Postgres.
2. Keep the default branch.

### Copy the *pooled* connection string

Neon → your project → **Connect** → choose **Pooled connection** (not
"Direct connection") → Database `forexai`. The URI looks like:

```
postgresql://USER:PASSWORD@ep-xxx-pooler.region.aws.neon.tech/forexai?sslmode=require
```

> ⚠️ **The `-pooler` suffix is not optional.** Render's free instances are
> IPv6-only and cannot reach Neon's direct endpoint at all, so the direct
> host will fail to resolve. If a hostname "does not exist" on Render, check
> this suffix first.

Both services read the same database through **different variables**, and
each variable must hold **its own field** — putting the username in the
database field produces `database "<username>" does not exist`.

| Service | Variable | Value |
| --- | --- | --- |
| `forexai-csharp-api` | `ConnectionStrings__ForexAiDatabase` | the full URI (key=value form also works) |
| `forexai-python-ai` | `RAG_DB_HOST` | `ep-xxx-pooler.region.aws.neon.tech` |
| | `RAG_DB_PORT` | `5432` |
| | `RAG_DB_NAME` | `forexai` — **the database**, not the user |
| | `RAG_DB_USER` | the user from the URI |
| | `RAG_DB_PASSWORD` | the password, **decoded** (not URL-encoded) |

> **TLS is handled for you on both paths.** The Python service sets
> `sslmode=require` in code (`RAG_DB_SSLMODE`, default `require`), so no
> `sslmode` value is needed in any `RAG_DB_*` variable. The .NET side takes
> the URI as-is. Both are required for Neon, which refuses a plaintext
> handshake — if you ever see `connection is insecure (try using
> sslmode=require)` from a hosted service, that guarantee has been bypassed.

---

## 3. Deploy with the blueprint

Render → **New → Blueprint** → select this repository → **Apply**.

`render.yaml` at the repository root defines three web services:

| Service | Type | Plan | Health check |
| --- | --- | --- | --- |
| `forexai-python-ai` | web | free | `/ready` |
| `forexai-csharp-api` | web | free | `/health` |
| `forexai-dashboard` | web | free | `/health` |

> **Creating a service by hand instead of using the blueprint?** Set these
> three fields per service, or the build fails with
> `open Dockerfile: no such file or directory` — this repository has **no
> root `Dockerfile`**, each one lives in a subdirectory:
>
> | Service | Language | Root Directory | Dockerfile Path |
> | --- | --- | --- | --- |
> | `forexai-python-ai` | Docker | `forexai-ai` | `forexai-ai/Dockerfile` |
> | `forexai-csharp-api` | Docker | `ForexAI` | `ForexAI/Dockerfile` |
> | `forexai-dashboard` | Docker | `forexai-dashboard` | `forexai-dashboard/Dockerfile` |
>
> **Dockerfile Path is relative to the repository root**, not to the Root
> Directory (Render documents it as `my-subdirectory/Dockerfile`), while Root
> Directory becomes the build context.

Render prompts for every value marked `sync: false`. Fill them in as:
**python-ai**
- `TWELVE_DATA_API_KEY`, `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODELS`
- `RAG_DB_HOST` (pooler host only), `RAG_DB_USER`, `RAG_DB_PASSWORD`
- `CORS_ALLOWED_ORIGIN` = `https://forexai-dashboard.onrender.com`
- `AI_SERVICE_API_KEY` → **auto-generated; copy the value**

**csharp-api**
- `ConnectionStrings__ForexAiDatabase`
- `PythonApi__ApiKey` → **paste the generated `AI_SERVICE_API_KEY`**
- `Cors__AllowedOrigins__0` = `https://forexai-dashboard.onrender.com`

> ⚠️ **The two API keys must match exactly.** If `csharp-api` sends the wrong
> (or no) `X-API-Key`, every analysis returns `401` from the Python guard.



---

## 4. Keep the free tier awake

Free Render services spin down after ~15 minutes idle, so the first visitor
after a quiet period waits ~50 s for a cold start. UptimeRobot (free, 5-minute
interval) prevents that:

1. UptimeRobot → **Add New Monitor** → HTTP(s).
2. Add `https://forexai-dashboard.onrender.com/health` and
   `https://forexai-python-ai.onrender.com/ready`, interval 5 minutes.

Neon also auto-suspends after ~5 minutes idle; the first request afterwards is
1–3 s slower. Harmless.

---

## 5. Connect your PC (MT5 execution)

The bridge runs on **your Windows machine**, not in the cloud: the
`MetaTrader5` package is Windows-only and talks to a local terminal over IPC.

```powershell
# 1. Open MT5 and log into your DEMO account (Algo Trading enabled)

# 2. In forexai-ai/, put this in .env
#    BRIDGE_TOKEN=<the token you generated in step 0>
#    MT5_DRY_RUN=true          # keep this until you trust the payloads

# 3. Start the bridge (dry-run by default - nothing is sent)
python scripts/run_signal_bridge.py --token <BRIDGE_TOKEN>

# 4. In a second terminal, expose it over HTTPS
winget install --id Cloudflare.cloudflared   # once
cloudflared tunnel --url http://127.0.0.1:8799
```

cloudflared prints a URL such as
`https://random-words-1234.trycloudflare.com`. Your signal target is:

```
https://random-words-1234.trycloudflare.com/signal?token=<BRIDGE_TOKEN>
```

> The hostname is **random and changes on every restart**. `WEBHOOK_ALLOWLIST`
> is already set to `.trycloudflare.com` in `render.yaml` to cover this; just
> paste the new URL into your request each session.

### End-to-end test (dry-run)

Ask the hosted service for a signal with that webhook URL — from the
dashboard's analysis request, or directly:

```powershell
curl.exe -X POST https://forexai-csharp-api.onrender.com/api/analysis `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer <your JWT>" `
  -d '{
        "forex_pair_id": "11111111-1111-1111-1111-111111111111",
        "symbol": "EURUSD",
        "timeframe": "FifteenMinutes",
        "webhook_url": "https://random-words-1234.trycloudflare.com/signal?token=<BRIDGE_TOKEN>"
      }'
```



---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `failed to read dockerfile: open Dockerfile: no such file or directory` | The repo root has no `Dockerfile`; each service's lives in a subdirectory, so a service created with defaults builds from the root and fails immediately | Set **Root Directory** + **Dockerfile Path** per service (see below), or deploy via the blueprint, which sets both |
| Build log shows an old commit (e.g. `Checking out commit a4a3731`) | The service predates newer commits, or auto-deploy is off | **Manual Deploy → Deploy latest commit**, and confirm `autoDeploy: true` |
| `SSL_do_handshake() failed ... SSL alert number 40` / `no live upstreams` in the dashboard nginx log | A proxied `location` is missing `proxy_ssl_server_name on;`, so Render's edge rejects the handshake | Add the directive to every location with an `https://` upstream (`/api/` and `/health`); `test_dashboard_nginx.py` enforces this |
| `AmbiguousMatchException: The request matched multiple endpoints` on `GET /health` | Two endpoints claim the same route (e.g. a `MapGet("/health")` alongside `HealthController`) | Remove the duplicate; `/health` is served by `HealthController`. `HealthEndpointTests` fails if this regresses |
| `Hosting failed to start` / `TaskCanceledException at KestrelServerImpl.BindAsync` | Usually a symptom: the health endpoint 500s, so the deploy restarts in a loop until it times out | Fix whatever `/health` is returning — `curl https://forexai-csharp-api.onrender.com/health` |
| `free not a valid plan for service type cron` | A cron service in `render.yaml` | Migrations moved to `.github/workflows/db-migrate.yml`; remove the cron block |
| Migration workflow fails on `Jwt__Key` | Repository secret missing | Add `JWT_KEY` and `NEON_CONNECTION_STRING` under repo Settings → Actions |
| `401` on `/analysis` | `PythonApi__ApiKey` ≠ `AI_SERVICE_API_KEY` | Copy the python-ai key into csharp-api and redeploy |
| Build fails with `HTTP 404 ... MODEL_ARTIFACTS_BASE_URL` | No `models-v1` release assets yet | Step 1 of this guide |
| `Webhook delivery skipped: host not in WEBHOOK_ALLOWLIST` | Wrong tunnel host or unset allowlist | Keep `.trycloudflare.com`; check the URL you pasted |
| Bridge answers `401` | Missing/incorrect `?token=` | Use the same `BRIDGE_TOKEN` you started the bridge with |
| `502` on proxied paths that are otherwise healthy | A proxied `location` missing `proxy_ssl_server_name on;` | Send SNI on every `https://` upstream; `test_dashboard_nginx.py` enforces this |
| Every `/api/*` call returns `508` / `x-render-routing: loop` | A proxied `location` forwards the *dashboard's* `Host`; Render's edge routes by `Host` and sends it back | Use `proxy_set_header Host $proxy_host;` so the edge routes to the API |
| nginx logs `499` and the deploy never goes healthy | `/health` proxied to another service, so the probe had to wake a free-tier instance and Render gave up first | Serve `/health` locally; a liveness probe must not depend on a downstream |
| Dashboard restarts every ~60 s (`Detected a new open port`) | `listen 80` while Render injects `PORT` (10000) | `listen ${PORT}`, with `ENV PORT=80` in the dashboard Dockerfile |
| `GET /api/ForexPairs` returns `[]` and the picker is empty | Migrations created `forex_pairs` but nothing ever inserted a row | The pairs are seeded via EF `HasData`; re-run the migration workflow after pulling |
| A pair in the picker `400`s when selected | The picker (database) and the Python currency map are separate lists | Add the currency to `app/fundamentals/currency_map.py`; a test keeps the two in sync |
| `psycopg` error naming host `postgres` | `RAG_DB_HOST` still holds the Docker Compose *service name* | Set it to the Neon **pooler** host |
| `database "<username>" does not exist` | `RAG_DB_NAME` holds the username | Set `RAG_DB_NAME=forexai` — the database name, one field per variable |
| `password authentication failed` from psycopg | `RAG_DB_USER` / `RAG_DB_PASSWORD` hold the Compose values | Copy the Neon user and decoded password from the connection details |
| `connection is insecure (try using sslmode=require)` | The RAG store connected without TLS | The service sets `sslmode=require` itself; check nothing overrides `RAG_DB_SSLMODE` |
| Migration workflow fails after a full build | A secret was empty or malformed | The workflow now preflights in ~2 s and names the variable; check `NEON_CONNECTION_STRING` and `JWT_KEY` (≥32 bytes) |
| `503` from `/analysis` on a hosted service | Missing `OPENROUTER_API_KEY` / `TWELVE_DATA_API_KEY` | `/ready` names the missing variable |
| Dashboard blank, `/api` 502 | `CSHARP_API_URL` wrong, or csharp-api still building | Point it at `https://forexai-csharp-api.onrender.com` |
| First request slow (~50 s) | Free service spun down | UptimeRobot monitor (step 4) |
| Docker build fails on `COPY models` | `models/` not in the build context | Ensure `ARTIFACTS.sha256` is committed |

## Security notes

- No secrets are committed: `render.yaml` prompts for every value
  (`sync: false`), `.env` is git-ignored, and `.dockerignore` keeps `.env`
  out of image layers.
- `AI_SERVICE_API_KEY` protects the public Python service from burning your
  OpenRouter credit.
- `WEBHOOK_ALLOWLIST` is deny-all by default; a wildcard entry is required
  only because a quick-tunnel hostname cannot be enumerated.
- The bridge refuses `/signal` without a token, so keep `BRIDGE_TOKEN` long.
- Trading stays on your PC: nothing but analysis runs in the cloud.

## Local development is unchanged

`docker compose up` still works. The nginx upstream is now an environment
variable that **defaults** to `http://csharp-api:8080`, so no compose edits
were needed, and `MARKET_DATA_PROVIDER` still defaults to `twelve`.

Run the gates before pushing:

```powershell
cd forexai-ai
python -m ruff check app tests scripts
python -m pytest -q                      # 331 tests
python scripts/check_mt5_market_data.py # local MT5 smoke test

cd ..\ForexAI
dotnet build
dotnet test
```

You should see, in the bridge terminal:

```
MT5 connected: login=... balance=...
DRY-RUN: EURUSD buy market ... NOT sent
```

and the signal returned to the caller. Verify the rejection paths too: a
`HOLD` signal returns `400`, and a wrong token returns `401`.

### Going live (demo account only)

1. In `forexai-ai/.env`: `MT5_DRY_RUN=false`
2. Restart the bridge with `--live`.

Every order still passes the risk gates: `approved=true` from the risk agent,
mandatory SL/TP, optional confidence floor, and the entry-drift guard.

After the first deploy, apply the database migrations from GitHub Actions
(**Actions → Database migrations → Run workflow**), then verify:

```powershell
curl.exe https://forexai-python-ai.onrender.com/ready
curl.exe https://forexai-csharp-api.onrender.com/health
curl.exe https://forexai-dashboard.onrender.com/health
```

Create the first user account through the dashboard (or seed it via SQL).

> The workflow needs two **repository secrets** (Settings → Secrets and
> variables → Actions): `NEON_CONNECTION_STRING` and `JWT_KEY`. Set them
> before the first run.
>
> Prefer to migrate from your own machine instead? Same command, no CI:
> ```powershell
> $env:ConnectionStrings__ForexAiDatabase = "<neon pooler connection string>"
> $env:Jwt__Key = "<the value Render generated>"
> dotnet run --project ForexAI/ForexAI.Api/ForexAI.Api.csproj -- --migrate
> ```
