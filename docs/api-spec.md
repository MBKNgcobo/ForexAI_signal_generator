# ForexAI API Specification

Base URL (local compose): `http://localhost:8080`
AI service (internal/direct): `http://localhost:8001`

Auth: `Authorization: Bearer <JWT>` for all `/api/*` routes except register/login/health.
Internal Python service optionally requires `X-API-Key: <AI_SERVICE_API_KEY>`.

Error envelope (C# API): `{ "message": "<human-readable reason>" }`
Error envelope (Python): `{ "detail": "<reason>" }` (FastAPI validation: `422` with `detail` array).


## 1. Auth — Login (public)

`POST /api/auth/login`

**Headers:** `Content-Type: application/json` (no auth header).

**Request body:**

```json
{
  "email": "demo@forexai.local",
  "password": "Demo123!"
}
```

**Success — `200 OK`:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock",
  "expiresAt": "2026-10-04T10:00:00Z",
  "email": "demo@forexai.local",
  "displayName": "Demo Trader"
}
```

**Error — `401 Unauthorized`:**

```json
{ "message": "Invalid email or password." }
```

Related: `POST /api/auth/register` with `{ "email", "displayName", "password" }` returns `200` on success and `400 { "message" }` when the email is taken.


## 2. Signals — Paged History (GET with query params, protected)

`GET /api/signals?page=1&pageSize=10&status=Generated`

**Headers:** `Authorization: Bearer <JWT>`.

**Query parameters:**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `page` | int, >= 1 | No (default `1`) | Page number |
| `pageSize` | int, 1–100 | No (default `10`) | Items per page |
| `status` | enum `Generated, UnderReview, Accepted, Rejected` | No | Filter by lifecycle status |

**Success — `200 OK`:**

```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "symbol": "EURUSD",
      "direction": "Buy",
      "confidence": 0.78,
      "entryPrice": 1.0852,
      "stopLoss": 1.0821,
      "takeProfit": 1.0914,
      "status": "Generated",
      "createdAt": "2026-10-03T09:12:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "pageSize": 10
}
```

**Error — `401 Unauthorized`:**

```json
{ "message": "Unauthorized" }
```


## 3. Analysis — Generate Signal (protected POST)

`POST /api/analysis`

**Headers:** `Authorization: Bearer <JWT>`, `Content-Type: application/json`.

**Request body:**

```json
{
  "forex_pair_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "symbol": "EURUSD",
  "timeframe": "OneHour"
}
```

**Success — `200 OK`:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "OneHour",
  "technical_analysis": { "direction": "Buy", "confidence": 0.72, "summary": "EMA cross up, RSI 58." },
  "fundamental_analysis": { "direction": "Buy", "confidence": 0.61, "summary": "USD soft on CPI miss." },
  "quant_prediction": { "direction": "Buy", "confidence": 0.69, "summary": "Ensemble favours upside." },
  "risk_assessment": {
    "risk_level": "Medium", "approved": true, "agreement": 0.8,
    "reason": "Majority agreement, R:R 2.0.",
    "entry_price": 1.0852, "stop_loss": 1.0821, "take_profit": 1.0914, "risk_reward": 2.0
  },
  "final_decision": { "direction": "Buy", "confidence": 0.74, "reasoning": "Aligned agents, gate passed." }
}
```

**Error — `400 Bad Request`:**

```json
{ "message": "Unsupported symbol 'ZZZUSD'." }
```

**Error — `401 Unauthorized`:**

```json
{ "message": "Unauthorized" }
```

**Error — `503 Service Unavailable` (AI provider down):**

```json
{ "message": "AI provider is rate-limited or unavailable. Please retry shortly." }
```

Direct Python equivalents: `POST /analysis` (`422` on bad shape, `400` unsupported pair, `502` bad LLM output, `503 + Retry-After` degraded) and `GET /market-data/EURUSD?timeframe=OneHour&limit=100`.


## Status Codes

| Code | Meaning in ForexAI |
| ---- | ------------------ |
| 200 | Success |
| 400 | Unsupported pair / domain rule violated |
| 401 | Missing or invalid JWT (or `X-API-Key` on Python service) |
| 404 | Signal not found |
| 422 | Schema validation failed (bad symbol shape, timeframe, limit) |
| 502 | Upstream LLM returned unusable output |
| 503 | Degraded dependency (market data / LLM / DB), retry with `Retry-After: 30` |




