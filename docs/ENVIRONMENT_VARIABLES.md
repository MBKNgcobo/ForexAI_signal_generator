# ForexAI — Environment Variables Reference

One file configures everything: `.env` next to `docker-compose.yml`
(copied from `.env.example` by `start.bat`). Never edit source code to
configure the system. Never commit `.env`.

Format per variable: purpose, required?, example, where the client gets it.

## A. Client-safe settings (free to change)

```text
Variable: DASHBOARD_PORT
Purpose: Host port for the dashboard (the ONLY port on all interfaces).
Required: No (default 80). Needs admin approval once on Windows; use 8080 to avoid it.
Example: DASHBOARD_PORT=8080
Where: You choose. Change only if the port is taken.

Variable: API_PORT
Purpose: Host port for the .NET API (127.0.0.1 only, debugging/health).
Required: No (default 8080).
Example: API_PORT=8080
Where: You choose.

Variable: AI_PORT
Purpose: Host port for the Python AI service (127.0.0.1 only, /health /docs).
Required: No (default 8001).
Example: AI_PORT=8001
Where: You choose.

Variable: POSTGRES_PORT
Purpose: Host port for PostgreSQL (127.0.0.1 only, backups).
Required: No (default 5434).
Example: POSTGRES_PORT=5434
Where: You choose.

Variable: CORS_ALLOWED_ORIGIN
Purpose: Browser origin allowed to call the API directly. Same-origin nginx
  proxy is the normal path, so the default is enough.
Required: No (default http://localhost).
Example: CORS_ALLOWED_ORIGIN=http://localhost
Where: Leave default unless support tells you otherwise.

Variable: LLM_PROVIDER
Purpose: Which LLM backend the AI service uses: openrouter | openai | http.
Required: No (default openrouter).
Example: LLM_PROVIDER=openrouter
Where: Leave default.

Variable: OPENROUTER_MODEL
Purpose: Primary reasoning model.
Required: No (default deepseek/deepseek-v4-flash-0731:free).
Example: OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731:free
Where: https://openrouter.ai/models

Variable: OPENROUTER_FALLBACK_MODELS
Purpose: Up to 3 comma-separated fallback models on rate-limit/outage.
Required: No (default empty).
Example: OPENROUTER_FALLBACK_MODELS=
Where: https://openrouter.ai/models

Variable: OPENROUTER_SITE_NAME / OPENROUTER_SITE_URL
Purpose: Attribution headers sent to OpenRouter.
Required: No.
Example: OPENROUTER_SITE_NAME=ForexAI / OPENROUTER_SITE_URL=http://localhost
Where: Leave default.

Variable: LOG_LEVEL
Purpose: Python service verbosity: DEBUG / INFO / WARNING / ERROR.
Required: No (default INFO).
Example: LOG_LEVEL=INFO
Where: You choose; DEBUG only when support asks.

Variable: FOREXAI_VERSION
Purpose: Version stamp on containers (compose ps).
Required: No (default v1.0.0).
Example: FOREXAI_VERSION=v1.0.0
Where: Set by release; leave alone.
```

## B. Secrets (SENSITIVE — never share, never commit)

```text
Variable: POSTGRES_PASSWORD
Purpose: Database password (compose + RAG store + backups).
Required: YES. Boot fails without it (compose :? guard).
Example: POSTGRES_PASSWORD=<long random string you make up>
Where: You invent it. 20+ chars, letters+numbers.

Variable: JWT_KEY
Purpose: Signs login tokens (C# API). Must differ from DB password, >=32 bytes.
Required: YES. Boot fails without it.
Example: JWT_KEY=<a different long random string>
Where: You invent it or `python -c "import secrets;print(secrets.token_urlsafe(32))"`.

Variable: TWELVE_DATA_API_KEY
Purpose: Market candles for /market-data + analysis graph. Missing -> 503.
Required: YES for live analysis (stack boots without it, analysis refuses).
Example: TWELVE_DATA_API_KEY=<key>
Where: https://twelvedata.com free account -> API key.

Variable: OPENROUTER_API_KEY
Purpose: AI reasoning for 3 specialists. Missing -> 503.
Required: YES for live analysis.
Example: OPENROUTER_API_KEY=<key>
Where: https://openrouter.ai sign in -> API keys.

Variable: AI_SERVICE_API_KEY
Purpose: Shared X-API-Key guard between C# API and Python service.
Required: No (empty = guard off, local default). Set it to enable.
Example: AI_SERVICE_API_KEY=
Where: You invent it; must be identical on both services (single .env key).

Variable: SOTW_API_KEY / BUSINESS_QUANT_API_KEY
Purpose: Optional fundamentals coverage.
Required: No.
Example: (empty)
Where: Respective providers; leave empty to skip.

Variable: RAG_DB_SSLMODE
Purpose: TLS mode for the AI -> Postgres RAG connection.
Required: No, BUT must stay "disable" for local compose (DB has no TLS).
  Managed Postgres (Neon) needs "require". Wrong value breaks /analysis.
Example: RAG_DB_SSLMODE=disable
Where: Leave default for the client install.

Variable: POSTGRES_DB / POSTGRES_USER / JWT_ISSUER / JWT_AUDIENCE
Purpose: Database name/user + token issuer/audience.
Required: No (defaults forexai/postgres/ForexAI/ForexAI).
Example: POSTGRES_DB=forexai
Where: Leave defaults.
```

## Reading /ready output

- `AI .../ready FAIL` + message naming `TWELVE_DATA_API_KEY` -> section B, fix `.env`, `start.bat`.
- `API .../health/ready FAIL` -> database or Python unreachable; check
  `POSTGRES_PASSWORD`/`JWT_KEY`, then `logs.bat`.
