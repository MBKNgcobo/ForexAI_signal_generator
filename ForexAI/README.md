# ForexAI — .NET 9 API

> Part of the **[ForexAI platform](../README.md)** · siblings: [`forexai-ai/`](../forexai-ai/README.md) (AI service) · [`forexai-dashboard/`](../forexai-dashboard/README.md) (frontend)

REST API that owns authentication, persistence and orchestration: it receives
trade requests from the dashboard, calls the Python AI service for a signal,
and stores the result for review and audit.

Built as **Clean Architecture** — domain rules know nothing about EF Core or
HTTP — with an xUnit test project covering the domain and repository layers.

## Projects

| Project | Responsibility |
| --- | --- |
| `ForexAI.Domain` | Entities (`TradingSignal`), value rules, repository interfaces. |
| `ForexAI.Application` | Use cases (`AnalyzeMarketService`), DTO/contracts, cross-cutting interfaces. |
| `ForexAI.Infrastructure` | EF Core (`ForexAiDbContext` + Npgsql), repositories, Identity stores, HTTP client to the AI service. |
| `ForexAI.Api` | Controllers, JWT/Identity wiring, OpenAPI, `Program.cs` composition root. |
| `ForexAI.Tests` | xUnit tests for the domain and repository behaviour. |

## Endpoints

| Method | Route | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `api/Auth/register` · `api/Auth/login` | — | Identity + JWT issuance. |
| `POST` | `api/Analysis` | — | Runs the AI pipeline and persists a signal. |
| `GET` | `api/Analysis/health` | — | Upstream AI service health. |
| `GET` | `api/ForexPairs` · `api/Timeframes` | — | Reference data for the dashboard. |
| `GET` | `api/MarketData/{symbol}` | — | Proxied candles. |
| `GET` | `api/Signals` · `api/Signals/status/{status}` · `api/Signals/{id}` | JWT | Signal review queue. |
| `POST` | `api/Signals/{id}/accept` · `api/Signals/{id}/reject` | JWT | Human decision on a signal. |
| `GET` | `api/Signals/{id}/audit` | JWT | Audit trail for a signal. |
| `GET` | `/health` · `/health/ready` | — | Liveness / readiness probes. |

## Configuration

Configuration is layered (`appsettings.json` → `appsettings.{Environment}.json`
→ environment variables). **No credentials are stored in source control.**

| Key | Provided by | Purpose |
| --- | --- | --- |
| `ConnectionStrings__ForexAiDatabase` | `docker-compose.yml` env | PostgreSQL connection. |
| `Jwt__Key` / `Jwt__Issuer` / `Jwt__Audience` | `docker-compose.yml` env | Token signing (key must be ≥ 32 bytes). |
| `PythonApi__BaseUrl` | env or appsettings | Base URL of the AI service (`http://python-ai:8000` in compose). |
| `Cors__AllowedOrigins__0` | env | Allowed browser origin. |
| `DevelopmentUser__UserId` | appsettings | Fixed user id used when running without a bearer context. |

For local development without Docker, use user secrets:

```bash
cd ForexAI
dotnet user-secrets set "ConnectionStrings:ForexAiDatabase" "Host=localhost;Port=5434;Database=forexai;Username=postgres;Password=<password>" --project ForexAI.Api
dotnet user-secrets set "Jwt:Key" "<at least 32 random bytes>" --project ForexAI.Api
```

> **Rotate any credential that was ever committed.** Configuration values that
> used to live in `appsettings.json` were removed from source control; the
> history of the previous repository still contains them.

## Run

```bash
# as part of the platform (recommended)
docker compose up -d          # from the repository root

# or standalone
cd ForexAI
dotnet run --project ForexAI.Api
```

## Test

```bash
cd ForexAI
dotnet test
```
