# ForexAI — Dashboard

> Part of the **[ForexAI platform](../README.md)** · siblings: [`ForexAI/`](../ForexAI/README.md) (.NET API) · [`forexai-ai/`](../forexai-ai/README.md) (AI service)

React 19 + TypeScript SPA for traders: candle charts, the AI analysis breakdown,
and a human review queue for incoming signals.

## Features

- **Auth** — register / login against the .NET API, JWT stored and attached via an authenticated fetch wrapper (`src/auth/`).
- **Market chart** — candles rendered with [lightweight-charts](https://github.com/tradingview/lightweight-charts), pair and timeframe selectors (`components/market/`).
- **Analysis breakdown** — one panel per specialist (technical / fundamental / quant), plus the risk assessment (entry, stop-loss, take-profit, risk:reward) and the final decision (`components/analysis/`).
- **Signal workflow** — review queue, detail view and accept / reject actions with an audit trail (`components/signals/`).

## Stack

React 19 · TypeScript 6 · Vite 8 · lightweight-charts 5 · oxlint — served by
nginx in Docker.

## Development

```bash
npm install
npm run dev          # http://localhost:5173
```

The API base URL comes from `VITE_API_BASE_URL` and defaults to `""`
(same-origin). In development either point it at the API or proxy `/api` —
see `vite.config.ts`.

```bash
npm run build        # tsc -b && vite build  → dist/
npm run lint         # oxlint
npm run preview      # serve the production build locally
```

## Docker

The image builds the SPA and serves `dist/` with nginx. `nginx.conf`
proxies:

| Path | Target |
| --- | --- |
| `/api/*` | `http://csharp-api:8080/api/*` (5-minute timeouts — AI analysis can be slow) |
| `/health` | `http://csharp-api:8080/health` |
| everything else | SPA fallback to `index.html` |

Because the browser only ever talks to nginx, no CORS configuration is needed
in production.

## Structure

```
src/
├── auth/           auth API, token storage, authenticated fetch
├── components/
│   ├── analysis/   agent, risk and final-decision panels
│   ├── auth/       login screen
│   ├── market/     chart + market panel
│   └── signals/    history, detail, review / accept-reject
├── config/         API base URL
├── pages/          Dashboard composition root
├── services/       typed API clients (signals, pairs, timeframes, audit…)
└── types/          shared TypeScript contracts
```
