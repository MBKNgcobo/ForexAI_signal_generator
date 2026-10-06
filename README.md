<div align="center">

# ForexAI — AI-Powered Forex Trading Platform

**A full-stack trading platform: a React dashboard, a .NET 9 Clean Architecture API, and a Python AI microservice that turns market data into risk-gated trading signals.**

![CI](https://github.com/MBKNgcobo/ForexAI_signal_generator/actions/workflows/ci.yml/badge.svg)
![.NET](https://img.shields.io/badge/.NET-9.0-512BD4?logo=dotnet&logoColor=white)
![Python](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-346-brightgreen)


</div>

---

## Overview

ForexAI is a monorepo containing the whole platform. A trader picks a pair and
timeframe in the browser; the dashboard calls a .NET API which persists signals
and forwards the request to a Python AI service. That service runs a six-node
LangGraph pipeline — candle data, three independent specialists (technical,
fundamental, quant), a risk gate, and a final decision — and returns a single
recommendation with entry price, stop-loss, take-profit and reasoning.

Every layer is deployable on its own and the whole stack boots with one command.


## Architecture

```mermaid
flowchart TD
    subgraph DB ["Database Layer"]
        pg_db[(PostgreSQL 17 :5432)]
    end

    subgraph API ["Backend API"]
        dotnet[.NET 9 Clean Architecture]
    end

    dotnet -->|EF Core| pg_db
```

| Component | Path | Stack | Role |
| --- | --- | --- | --- |
| **Dashboard** | [`forexai-dashboard/`](./forexai-dashboard) | React 19 · TypeScript · Vite · lightweight-charts · nginx | Charts, signal history, request flow for the trader. |
| **API** | [`ForexAI/`](./ForexAI) | .NET 9 · Clean Architecture (Api / Application / Domain / Infrastructure) · xUnit | Auth (JWT), persistence, orchestration of the AI service, migrations. |
| **AI service** | [`forexai-ai/`](./forexai-ai) | Python 3.14 · FastAPI · LangGraph · scikit-learn / XGBoost | Market data, multi-agent analysis, risk gating, signal generation. |
| **Compose stack** | [`docker-compose.yml`](./docker-compose.yml) | Docker Compose | Wires all of the above together with PostgreSQL. |

<a id="quick-start"></a>
## Quick start

**Requirements:** Docker Desktop (Windows/macOS) or Docker Engine + Compose v2
(Linux). For a full run you also need API keys — see [Configuration](#configuration).

### Windows (recommended for clients)

```bat
:: From the folder that contains docker-compose.yml:
scripts\start-forexai.bat
```

The script verifies Docker is running, creates `.env` from `.env.example` on
first run and opens it for editing, refuses to start while placeholder values
remain, builds everything, waits until all four services are healthy, then
opens the dashboard. Full walkthrough:
[`docs/client-installation.md`](./docs/client-installation.md).
Day-to-day use in plain English: [`docs/user-guide.md`](./docs/user-guide.md).

### Any platform (manual)

```bash
git clone https://github.com/MBKNgcobo/ForexAI_signal_generator.git
cd ForexAI_signal_generator

cp .env.example .env      # then fill in real values
docker compose up -d --build
```

| Service | URL | Bound to |
| --- | --- | --- |
| Dashboard | http://localhost | all interfaces (`DASHBOARD_PORT`, default 80) |
| .NET API health | http://localhost:8080/health | 127.0.0.1 only (`API_PORT`) |
| AI service | http://localhost:8001 (`/health`, `/docs`) | 127.0.0.1 only (`AI_PORT`) |
| PostgreSQL | localhost:5434 | 127.0.0.1 only (`POSTGRES_PORT`) |

`docker compose up` builds every image, waits for PostgreSQL to become healthy,
runs the EF Core migration job (the one-shot `db-migrate` service), then starts
the API — which refuses to serve until the migration succeeded — and the
dashboard. API, AI and PostgreSQL listen on 127.0.0.1 only; the dashboard is
the sole network-facing entry point.

### Everyday operations

| Task | Command |
| --- | --- |
| Status + health checks | `scripts\status-forexai.bat` or `docker compose ps` |
| Follow logs | `docker compose logs -f --tail 100 <service>` |
| Apply a `.env` change | `scripts\start-forexai.bat` (plain restart keeps old env) |
| Stop (keeps all data) | `scripts\stop-forexai.bat` |
| Update code + images | `scripts\update-forexai.bat` |
| Database backup | `scripts\backup-forexai.bat` → `backups\forexai-<timestamp>.sql` |
| Create a dashboard account | `scripts\add-user-forexai.bat` |

**Data safety.** All data lives in the named volume
`forexai_forexai-postgres-data`; it survives restarts, updates and
`docker compose down`. Never run `docker compose down -v` — that deletes it.
The compose project name is pinned (`name: forexai`), so renaming or moving
the folder does not orphan the volume.

**Version & rollback.** Containers are stamped with the `FOREXAI_VERSION`
label from `.env`. To roll back a bad update: `git checkout <previous-tag>`,
then run the start script again — the database volume is untouched.

**Troubleshooting:**

| Symptom | Likely cause / fix |
| --- | --- |
| `port is already in use` | Another program owns the port — set `DASHBOARD_PORT` (or `API_PORT`, `AI_PORT`, `POSTGRES_PORT`) in `.env`, run the start script again. |
| Start script: placeholders found | Fill in the listed values in `.env` (Notepad opens automatically). |
| Dashboard opens but analysis fails | Run `scripts\status-forexai.bat` — `GET /health/ready` names the missing dependency (API keys, database, AI service). |
| `/analysis` returns 503 with an `sslmode` error | `RAG_DB_SSLMODE` must stay `disable` for the bundled database — see `docker compose logs python-ai`. |
| Stack refuses to start after an update | `docker compose logs db-migrate` — a failed migration deliberately blocks the API instead of serving against a half-migrated database. |

### Develop locally

```bash
# AI service — hot reload, independent of the stack
cd forexai-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# API
cd ForexAI
dotnet run --project ForexAI.Api

# Dashboard
cd forexai-dashboard
npm install && npm run dev
```

See each component's README for detail: [forexai-ai](./forexai-ai/README.md) · [ForexAI](./ForexAI/README.md) · [forexai-dashboard](./forexai-dashboard/README.md).

## How a signal is produced

1. **Fetch** — candles come from Twelve Data with a 30-second TTL cache; timestamps are normalised across six timeframes.
2. **Specialise** — three agents form opinions independently: technical (EMA / RSI / ATR), fundamental (World Bank + optional PostgreSQL RAG evidence), quant (21-feature ensemble of logistic regression, random forest and XGBoost).
3. **Gate** — the risk agent requires a directional majority, scores agreement, checks minimum risk:reward, derives stop-loss (1.0× ATR) and take-profit (1.5× ATR), and applies an explicit veto when a strong quant signal opposes the majority.
4. **Decide** — the decision agent emits one direction, a confidence and a written rationale, or `NO_TRADE`.
5. **Persist** — the .NET API stores the signal and returns it to the dashboard.

<a id="configuration"></a>
## Configuration

The root `.env` (create it from [`.env.example`](./.env.example)) feeds
`docker-compose.yml`. The essentials:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `POSTGRES_*` / `DATABASE_PASSWORD_URLENCODED` | API, AI, DB | Database credentials (compose does **not** URL-encode for you). |
| `JWT_KEY` / `JWT_ISSUER` / `JWT_AUDIENCE` | API | Token signing for dashboard auth. |
| `TWELVE_DATA_API_KEY` | AI service | Candle data; missing → `503` on `/market-data`. |
| `LLM_PROVIDER` + keys | AI service | `openrouter` (default), `openai` or `http`, with fallback models and retries. |
| `SOTW_API_KEY` / `BUSINESS_QUANT_API_KEY` | AI service | Optional fundamentals sources. |
| `CORS_ALLOWED_ORIGIN` | API | Origin the dashboard calls from. |
| `DASHBOARD_PORT` / `API_PORT` / `AI_PORT` / `POSTGRES_PORT` | compose | Host ports (defaults 80 / 8080 / 8001 / 5434). |
| `AI_SERVICE_API_KEY` | API + AI | One value drives the optional `X-API-Key` guard on both sides. Empty = off. |
| `RAG_DB_SSLMODE` | AI service | TLS mode for the fundamentals RAG connection; must stay `disable` for the bundled database. |
| `LOG_LEVEL` | AI service | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`). |
| `FOREXAI_VERSION` | compose | Version label stamped on every container. |

Each component also has its own contract file — [`forexai-ai/.env.example`](./forexai-ai/.env.example)
documents every variable the AI service understands.

**Secrets never enter git or image layers:** `.env` is ignored at the repo root,
by each sub-project's `.gitignore`, and by every `.dockerignore`; credentials are
injected as runtime environment variables only.

<a id="testing"></a>
## Testing

```bash
# Python AI service — 346 hermetic tests, no network, no credentials
cd forexai-ai && python -m pytest -q

# .NET API — unit tests
cd ForexAI && dotnet test

# Dashboard — type-check, lint, build
cd forexai-dashboard && npm run build && npm run lint
```

GitHub Actions ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)) runs
the Python suite on every push and pull request. The suite fakes market data,
the LLM and the database, so CI needs no secrets.

## Repository layout

```
ForexAI_signal_generator/
├── docker-compose.yml        # postgres + api + ai service + dashboard
├── .env.example              # environment contract for compose
├── scripts/                  # Windows client scripts (start/stop/status/update/backup/add-user)
├── docs/client-installation.md # step-by-step client guide
├── docs/user-guide.md          # plain-English guide for users and owners
├── .github/workflows/ci.yml  # CI
├── ForexAI/                  # .NET 9 API (Clean Architecture + xUnit)
│   ├── ForexAI.Api/            # controllers, Program.cs, migrations
│   ├── ForexAI.Application/    # use cases, contracts, interfaces
│   ├── ForexAI.Domain/          # entities, domain rules
│   ├── ForexAI.Infrastructure/  # EF Core, repositories, external clients
│   └── ForexAI.Tests/           # xUnit suite
├── forexai-ai/               # Python AI microservice (FastAPI + LangGraph)
│   ├── app/agents/             # market data, technical, fundamental, quant, risk, decision
│   ├── app/api/                # routers, validation, X-API-Key guard
│   ├── app/llm/                # provider factory, retries, typed errors
│   ├── app/models/             # 21-feature engineering, LR/RF/XGBoost
│   └── tests/                  # 346-test hermetic suite
├── forexai-dashboard/        # React 19 + Vite + lightweight-charts
└── ForexAI_Architecture_v1.0/ # architecture documentation
```

## Engineering highlights

- **Fail-soft by design** — the AI service starts without credentials, keeps `/health` alive, and returns `503` with `Retry-After` from the endpoint that actually needs the missing dependency.
- **Validation at the HTTP boundary** — bad symbols, timeframes and limits are rejected with `422` before any paid LLM or provider call.
- **Typed error contract** — `400` unsupported input · `401` auth · `422` schema · `502` unusable LLM output · `503` degraded dependency.
- **Hermetic tests** — 346 Python tests with zero network access; CI runs without secrets.
- **Security** — optional constant-time `X-API-Key` guard, conditional CORS, JWT auth, non-root Docker images, secrets excluded from every image layer.
- **Clean Architecture** on the .NET side keeps domain rules independent of EF Core and the transport layer, with an xUnit suite covering the use cases.

## Roadmap

- [ ] Pluggable candle providers behind the existing `MarketDataProvider` interface.
- [ ] Contract tests generated from the OpenAPI schema to catch drift against the .NET client.
- [ ] Prometheus metrics and structured JSON logs across services.
- [ ] Per-symbol rate limiting and cache warm-up for the provider layer.

---

<div align="center">
<sub>Built by <a href="https://github.com/MBKNgcobo">MBKNgcobo</a> · ForexAI signal generator</sub>
</div>
