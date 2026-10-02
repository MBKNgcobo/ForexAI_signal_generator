# ForexAI — Visual Studio Implementation Plan

## Working rule

Do not try to build the whole multi-agent system at once. Each task below must end with something that compiles, runs, or can be tested.

## Phase 0 — Repository Setup

Create a repository named `ForexAI`.

Target structure:

```text
ForexAI/
├── ForexAI.sln
├── src/
│   ├── ForexAI.Api/
│   ├── ForexAI.Application/
│   ├── ForexAI.Domain/
│   ├── ForexAI.Infrastructure/
│   └── ForexAI.Tests/
├── ai/
│   └── forexai-ai/
├── frontend/
│   └── forexai-web/
├── database/
├── docs/
└── docker-compose.yml
```

### Task 0.1
Create the Git repository and initial README.

**Done when:** the repository has a clean initial commit and the README explains the four application boundaries.

### Task 0.2
Create the .NET solution and projects:

- `ForexAI.Api` — ASP.NET Core Web API.
- `ForexAI.Application` — application services/use cases.
- `ForexAI.Domain` — entities, enums, value objects and domain rules.
- `ForexAI.Infrastructure` — PostgreSQL, external APIs and service implementations.
- `ForexAI.Tests` — automated tests.

**Done when:** the solution builds with no errors.

## Phase 1 — Domain Model First

Implement only the domain concepts from the approved class diagram.

Start with:

- `ForexPair`
- `MarketCandle`
- `TechnicalIndicator`
- `MarketAnalysis`
- `TradingSignal`
- `Agent`
- `AgentRun`
- `MLModel`
- `ModelPrediction`
- `EconomicEvent`
- `User`
- `Portfolio`
- `Position`
- `Backtest`

Create enums for signal direction and signal status.

**Do not connect PostgreSQL yet.**

### Task 1.1
Create entities and enums.

**Done when:** the domain project compiles and contains no EF Core or HTTP dependencies.

### Task 1.2
Write domain unit tests for signal state transitions.

Example cases:

- Generated -> UnderReview is valid.
- UnderReview -> Accepted is valid.
- UnderReview -> Rejected is valid.
- Rejected -> Accepted is invalid.

**Done when:** all tests pass.

## Phase 2 — Database

Use PostgreSQL for persistence.

Create the initial schema/migrations for:

```text
users
forex_pairs
market_candles
technical_indicators
economic_events
market_analyses
agents
agent_runs
ml_models
model_predictions
trading_signals
portfolios
positions
backtests
audit_logs
```

### Task 2.1
Create `ApplicationDbContext` in Infrastructure.

### Task 2.2
Configure PostgreSQL connection using environment configuration.

### Task 2.3
Create and apply the first migration.

**Done when:** a fresh PostgreSQL database can be created from the migration and the application can connect successfully.

## Phase 3 — C# API Skeleton

Create:

```text
GET /api/health
GET /api/forex/pairs
GET /api/market/{pair}/latest
POST /api/analysis
GET /api/signals/{id}
POST /api/signals/{id}/accept
POST /api/signals/{id}/reject
```

Start with fake/in-memory service responses where necessary.

**Done when:** Swagger can execute every endpoint and invalid requests return controlled errors.

## Phase 4 — Python AI Service

Create a separate Python project:

```text
ai/forexai-ai/
├── app/
│   ├── main.py
│   ├── api/
│   ├── agents/
│   ├── graphs/
│   ├── models/
│   ├── indicators/
│   ├── schemas/
│   └── services/
├── tests/
└── requirements.txt
```

Use FastAPI and Pydantic.

### Task 4.1
Create `GET /health`.

### Task 4.2
Create `POST /ai/analyze` with the documented request/response contract.

### Task 4.3
Return a deterministic mock signal first.

**Done when:** C# can call Python and receive a validated JSON response.

## Phase 5 — LangGraph Skeleton

Build the graph with nodes representing:

```text
load_context
market_agent
technical_agent
fundamental_agent
quant_agent
risk_agent
decision_agent
persist_result
```

For the first graph, agents can return hard-coded/fixture data.

**Done when:** one complete graph execution produces one structured signal and every node can be identified in logs.

## Phase 6 — Deterministic Market Intelligence

Implement technical calculations outside the LLM:

- EMA/SMA
- RSI
- MACD
- ATR
- volatility
- support/resistance features

Add tests for indicator calculations using known fixture data.

**Done when:** indicators are reproducible and do not require an LLM.

## Phase 7 — Connect Your Own ML Model

Create a provider boundary such as:

```text
IModelPredictor
    ├── LocalModelPredictor
    ├── HttpModelPredictor
    └── HuggingFaceModelPredictor
```

Initially implement `LocalModelPredictor` around one of your own models.

**Done when:** Quant Agent receives a real model prediction with model name/version recorded.

## Phase 8 — LLM Provider Abstraction

Create:

```text
ILLMProvider
    ├── OpenAIProvider
    └── Local/HuggingFaceProvider
```

Keep LLM calls limited to interpretation/reasoning over structured evidence.

**Done when:** the same agent can run with a different configured provider without changing agent logic.

## Phase 9 — React Dashboard

Create the React TypeScript application with pages/components for:

```text
Dashboard
Market
Signals
Agents
Models
Backtesting
Settings
```

MVP screen:

```text
Pair selector
Latest price
Price chart
Signal
Confidence
Entry / SL / TP
Agent results
Accept / Reject
```

**Done when:** the user can select a pair, request an analysis and review the returned signal.

## Phase 10 — HITL + Audit

Connect the Accept and Reject buttons to the C# signal lifecycle.

Persist:

- user ID,
- signal ID,
- action,
- timestamp,
- previous status,
- resulting status.

**Done when:** every user decision is auditable.

## Phase 11 — Near-Live Data

Replace fixtures with a market-data adapter.

Keep the external provider behind an interface:

```text
IMarketDataProvider
```

Then implement one provider.

**Done when:** market data appears on the dashboard within the SRS target and failed provider calls are handled safely.

## Phase 12 — Memory

Implement session, short-term and long-term memory using PostgreSQL first.

Do not introduce vector storage until needed.

**Done when:** a second analysis can retrieve relevant previous context and the stored memory can be inspected in the database.

## Phase 13 — Testing

Required test layers:

```text
Domain unit tests
Application unit tests
API integration tests
Python agent tests
Python contract tests
Model evaluation tests
End-to-end API -> Python tests
React component tests
Backtests
```

Also test failure modes:

- stale market data,
- missing candles,
- invalid model output,
- LLM timeout,
- Python service unavailable,
- database unavailable,
- conflicting agents,
- rejected signal,
- expired signal.

## Phase 14 — Deployment

Containerise:

```text
react
api
python-ai
postgres
```

Start locally with Docker Compose.

Then choose inexpensive hosting only after the application works locally.

## First Coding Session

Your immediate coding target is **Phase 0 + Phase 1 only**.

### Definition of done

At the end of the first coding session you should have:

1. `ForexAI.sln`.
2. Five C# projects.
3. Domain entities and enums.
4. Signal state transition tests.
5. A clean build.
6. A Git commit describing the completed baseline.

Do not build React, LangGraph, brokers, or live market data yet. The purpose of the first session is to establish the domain and architecture correctly before infrastructure complexity is introduced.
