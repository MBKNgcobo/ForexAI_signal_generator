# ForexAI — AI-Powered Forex Trading Platform

> **Portfolio project** by [MBKNgcobo](https://github.com/MBKNgcobo) · React dashboard + .NET 9 API + Python AI microservice.

![.NET](https://img.shields.io/badge/.NET-9.0-512BD4?logo=dotnet&logoColor=white)
![Python](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-78%2B-brightgreen)

[Overview](#overview) · [Tech Stack](#tech-stack) · [Local Setup](#local-setup-guide) · [API Docs](./api-spec.md) · [Database](./database-schema.md) · [Challenges](#technical-challenges--lessons-learned)

---

## Live Demo

> **REPLACE BEFORE SUBMITTING:**

```text
Live app:  [PASTE YOUR DEPLOYED URL HERE, e.g. https://forexai-demo.up.railway.app]
Demo login — Email:    demo@forexai.local
Demo login — Password: Demo123!
```

---

## Overview

ForexAI turns raw market data into a **single, risk-gated trading recommendation**. A trader picks a pair (e.g. `EURUSD`) and timeframe in the browser; the React dashboard calls a .NET 9 API which authenticates the user, persists signals, and forwards the request to a Python FastAPI microservice.

That AI service runs a **six-node LangGraph pipeline** — candle data, three independent specialists (technical, fundamental, quant), a risk gate that can veto or downgrade, and a final decision — returning direction, confidence, entry/SL/TP and reasoning.

Every layer boots with one command (`docker compose up -d`), degrades gracefully without credentials (`/health` stays up, dependent endpoints return `503 + Retry-After`), and is covered by hermetic tests with zero network access in CI.

## Tech Stack

- **Frontend:** React 19, TypeScript, Vite, lightweight-charts 5, nginx
- **Backend API:** .NET 9, Clean Architecture (Api / Application / Domain / Infrastructure), EF Core, ASP.NET Identity + JWT Bearer, xUnit
- **AI Service:** Python 3.14, FastAPI, LangGraph, Pydantic v2, scikit-learn / XGBoost, Twelve Data + World Bank clients
- **Data:** PostgreSQL 17 (app data + full-text RAG store for fundamentals)
- **Infra / DevOps:** Docker + Docker Compose, GitHub Actions CI, Uvicorn, non-root images, healthchecks
- **Auth / Security:** JWT (C# API), optional `X-API-Key` guard (Python service), conditional CORS, secrets via runtime env only


## Local Setup Guide

**Prerequisites:** Docker + Docker Compose. For a full run you need free keys for Twelve Data and OpenRouter (see Configuration).

**1. Clone the repo**

```bash
git clone https://github.com/MBKNgcobo/ForexAI_signal_generator.git
cd ForexAI_signal_generator
```

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env — at minimum set:
# POSTGRES_PASSWORD, JWT_KEY, TWELVE_DATA_API_KEY, OPENROUTER_API_KEY
# Full key list: see docs/.env.example
```

**3. Start the whole platform**

```bash
docker compose up -d
docker compose ps
docker compose logs -f csharp-api python-ai
```

**4. Open the services**

| Service | URL |
| ------- | --- |
| Dashboard | http://localhost |
| .NET API | http://localhost:8080 |
| AI service health / docs | http://localhost:8001/health and /docs |
| PostgreSQL | localhost:5434 |


**5. Develop one service locally (optional)**

```bash
# AI service with hot reload
cd forexai-ai
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# .NET API
cd ForexAI
dotnet restore
dotnet run --project ForexAI.Api
```

```bash
# Dashboard
cd forexai-dashboard
npm install
npm run dev
```

**6. Run tests**

```bash
cd forexai-ai && python -m pytest -q
cd ../ForexAI && dotnet test
cd ../forexai-dashboard && npm run build && npm run lint
```

See [api-spec.md](./api-spec.md) and [database-schema.md](./database-schema.md) for integration details.


## Technical Challenges & Lessons Learned

**Fail-soft startup was the first production lesson.** The original service read environment variables in many modules and raised at import time, so a container started without an `.env` file crashed before it could even serve `/health`. Centralising config in one module, deferring provider construction to first request with caching, and returning `503 + Retry-After` with an actionable message from the endpoint that actually needs the missing key kept orchestrators happy and turned misconfiguration into a 30-second fix. I now treat boot-without-secrets as a first-class requirement.

**Validation belongs at the HTTP boundary, not mid-pipeline.** Unknown timeframes used to fail deep inside the provider after paid LLM work had already run, surfacing as opaque `500` errors; malformed symbols and unparseable model output behaved the same way. Moving checks into Pydantic validators and a typed error mapper produced a contract clients can code against — `400` unsupported pair, `401` bad key, `422` bad shape, `502` unusable model output, `503` degraded dependency — and eliminated an entire class of wasted external calls.

**Disagreement between agents is a feature, not an exception.** Forcing three specialists (EMA/RSI/ATR technicals, World Bank plus RAG fundamentals, LR/RF/XGBoost quant ensemble) through a risk gate with majority agreement, minimum risk-reward, ATR-derived stops, and an explicit veto on a strong opposing quant signal removed the temptation to average opinions away. Canonicalising feature columns in one module fixed silent train/serve drift, and faking market data, the LLM and the database gave a 78-test hermetic suite that runs in CI with no secrets — which is what lets me refactor the graph with confidence.

---

<div align="center"><sub>Built by <a href="https://github.com/MBKNgcobo">MBKNgcobo</a></sub></div>



