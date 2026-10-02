# ForexAI AI Service

FastAPI service that runs the ForexAI analysis graph: it fetches market data,
combines technical / fundamental / quant specialist opinions behind a risk
gate, and returns a single trading recommendation.

## Requirements

- Python 3.14 (see `Dockerfile`)
- A Twelve Data API key (market data)
- An LLM provider key (`openrouter` by default, see `.env.example`)
- PostgreSQL for the fundamental RAG store (optional at boot, required for
  fundamental analysis)

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env   # then fill in real values
uvicorn app.main:app --reload
```

The service logs a configuration summary at startup. Missing variables do
**not** crash the process: `/health` stays up and the endpoints that need the
missing value return `503` with an actionable message.

## Configuration

`.env.example` is the full environment contract. The important entries:

| Variable | Purpose |
| --- | --- |
| `TWELVE_DATA_API_KEY` | Market data provider. Missing → `503` on `/market-data` and in the graph. |
| `LLM_PROVIDER` + key(s) | `openrouter` (default), `openai` or `http`. |
| `RAG_DB_*` | PostgreSQL connection for fundamental evidence. |
| `CORS_ALLOWED_ORIGIN` | Comma-separated browser origins. Empty disables CORS. |
| `AI_SERVICE_API_KEY` | Optional shared secret. When set, `/analysis` and `/market-data` require `X-API-Key`. |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` (default `INFO`). |

Never commit `.env`; it is ignored by `.gitignore` and `.dockerignore`.

## API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe, always public. |
| `GET` | `/market-data/{symbol}` | `symbol` must be six letters (`EURUSD`). Query: `timeframe`, `limit` (1-500). Invalid input → `422`. |
| `POST` | `/analysis` | Body: `forex_pair_id` (legacy, unused), `symbol`, `timeframe`. Unsupported pair → `400`; unknown timeframe → `422`. |

Valid timeframes (both endpoints): `OneMinute`, `FiveMinutes`,
`FifteenMinutes`, `OneHour`, `FourHours`, `OneDay`.

### Error mapping

| Status | Meaning |
| --- | --- |
| `400` | Well-formed but unsupported symbol/pair. |
| `401` | `X-API-Key` missing or wrong (only when `AI_SERVICE_API_KEY` is set). |
| `422` | Schema validation failure (symbol shape, timeframe, `limit`). |
| `502` | The LLM returned unusable or incomplete output. |
| `503` | Missing configuration, rate-limited LLM, or exhausted market-data quota (`Retry-After` is sent). |

## Tests

```powershell
python -m pytest -q
```

The suite is hermetic — market data, the LLM and the database are all faked,
so no network access or credentials are required. `pyproject.toml` holds the
pytest configuration (`testpaths = ["tests"]`, `asyncio_mode = "auto"`).

## Docker

```powershell
docker build -t forexai-ai .
docker run -p 8000:8000 --env-file .env forexai-ai
```

The image copies only `app/` and `models/`, runs as a non-root user
(`appuser`, uid 10001) and declares a `HEALTHCHECK` against `/health`.

## Repository layout

```
app/
  agents/      specialist nodes (technical, fundamental, quant, risk, decision)
  api/         FastAPI routers, request guards
  fundamentals/ World Bank / RAG access
  graphs/      LangGraph composition of the agents
  llm/         provider factory, retry policy, error taxonomy
  models/      feature engineering and quant training/inference
  schemas/     pydantic contracts
  services/    market data provider, cache, response mapping
scripts/       manual data/ensemble checks (not collected by pytest)
tests/         pytest suite
```
