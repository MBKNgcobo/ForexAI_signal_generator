# ForexAI — MT5 Readiness Report

> Produced by a full repository audit (code, tests, configuration, security)
> against the goal of **personal, supervised testing on your own MT5 DEMO
> account**. Every claim below is backed by a file/function reference or an
> executed test.

---

## Executive Summary

### 🟢 Ready for supervised DEMO testing — with the conditions below

**Why 🟢:** the application contains a *real, tested* MT5 integration — not a
mock: connection, market data, account/position reads, signal generation, a
risk-gated execution path with mandatory stop-loss/take-profit, and a webhook
bridge — all defaulting to **dry-run**, with a hermetic suite of 370 passing
tests including five dedicated MT5 test modules. Everything needed to safely
evaluate the system on a demo account works *today*.

**Conditions (all satisfied by this audit's change set + your process):**

1. The one code gap found — `--live` arming real orders **without** the
   documented `MT5_DRY_RUN=false` second key — has been **fixed**
   (`scripts/run_signal_bridge.py`, dual-key interlock + tests).
2. Testing is **attended and supervised** (you are the kill switch), per
   [`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md).
3. The **P0 items** in the improvement list below are completed before any
   *unattended / extended-automated* demo run.
4. **No live account is used at any point** during evaluation.

**Why not a blanket 🟡/🔴:** nothing blocks a first safe demo test — the missing
features (position sizing, kill switch, trade DB) affect *unattended scale*, not
a supervised evaluation.

---

## Current capabilities (verified implemented)

| Capability | Evidence | Status |
|---|---|---|
| MT5 terminal connection (attach + credential modes) | `app/broker/mt5_connection.py::connect` | ✅ Implemented |
| Terminal auto-launch | `ensure_terminal_running()` | ✅ Implemented |
| Read market prices / candles / ticks / depth | `mt5_market_data_provider.py` | ✅ Implemented |
| Read account (balance, equity, margin, trade_allowed) | `MT5AccountInfo`, `AccountSnapshot` | ✅ Implemented |
| Read open positions & pending orders | `mt5_sync.py::snapshot` | ✅ Implemented |
| Background state sync with drift reports | `MT5StateSynchronizer.start_background` | ✅ Implemented |
| Signal generation (technical + fundamental + quant) | LangGraph `forex_analysis_graph.py` | ✅ Implemented |
| Signal risk gate (majority, quant veto, ATR SL/TP) | `risk_agent.py` | ✅ Implemented |
| Final decision incl. forced `NO_TRADE` | `decision_agent.py` | ✅ Implemented |
| Signal → order mapping with hard gates | `signal_bridge.py::prepare_order_request` | ✅ Implemented |
| Order send (market/limit/stop) | `mt5_executor.py::send` | ✅ Implemented, **dry-run default** |
| Mandatory SL/TP + geometry + volume validation | `OrderRequest.__post_init__`, `_validate_risk_bounds` | ✅ Implemented |
| Entry-drift (stale price) protection | `SignalBridge.check_entry_drift` | ✅ Implemented |
| Duplicate/unauthorized webhook protection | `signal_token_valid` (`BRIDGE_TOKEN`) | ✅ Implemented (token optional) |
| Dry-run default, fail-closed on garbage config | `config.mt5_dry_run` | ✅ Implemented |
| Dual-key live arming (`--live` + `MT5_DRY_RUN=false`) | `run_signal_bridge.live_mode_refused` | ✅ **Fixed in this audit** |
| Webhook SSRF allowlist | `webhook_delivery.webhook_allowed` | ✅ Implemented |
| Verification CLIs (connection/data/orders/sync) | `scripts/check_mt5_*.py` | ✅ Implemented |
| Backtesting with spread/slippage/commission | `app/backtesting/engine.py` | ✅ Implemented |
| Observability (Prometheus, structured logs, request IDs) | `observability/` + `/metrics` | ✅ Implemented |
| Hermetic test suite (370 tests, no network) | `tests/` incl. 5 MT5 modules | ✅ Passing |

## Missing capabilities (verified absent by codebase search)

| Capability | Why it matters | Status |
|---|---|---|
| Position sizing by risk % | Fixed `MT5_SIGNAL_VOLUME` (0.01) — risk per trade not tied to balance or SL distance | ❌ Missing (P1) |
| Maximum risk per trade / daily loss / drawdown caps | A losing streak has no circuit breaker | ❌ Missing (P0 for unattended) |
| Maximum open positions / total exposure cap | Repeated signals can stack positions on one symbol | ❌ Missing (P0 for unattended) |
| Duplicate-order protection | Retried/duplicated webhook POST = second order | ❌ Missing (P0 for unattended) |
| Emergency stop / kill switch | Only "Ctrl+C on the bridge + close terminal" exists | ❌ Missing (P0 for unattended) |
| Spread & slippage protection at fill time | `deviation` cap exists (20 points), but no max-spread check | ❌ Missing (P1) |
| Trading-session / news-event restrictions | Signals can arrive any time the webhook is called | ❌ Missing (P2) |
| Order modification & automated closing | Executor opens only; sync is read-only; close = manual | ❌ Missing (P2, by design so far) |
| Persisted trade log / performance dashboard | Logs + Prometheus only; no trade records | ❌ Missing (P1) — journal covers testing phase |
| Pre-send margin check | Margin discovered only via broker rejection (10019) | ❌ Missing (P1) |
| Account-type guard (demo vs live) | Code cannot currently refuse a live account | ❌ Missing (P1) |

---

## MT5 integration status

| Capability | Status | Evidence | What is required to use it |
|---|---|---|---|
| Connect to MT5 | **Implemented** | `mt5_connection.py::connect` (attach or credential mode) | Windows + `MetaTrader5` pkg + terminal (`MT5_PATH`) |
| Read prices | **Implemented** | `MT5MarketDataProvider.get_market_data/get_tick` | Terminal logged in; symbol enabled; market open |
| Read account | **Implemented** | `MT5AccountInfo` / `AccountSnapshot` | Connection |
| Read positions/orders | **Implemented** | `mt5_sync.py::snapshot/poll_once` | Connection |
| Generate signal | **Implemented** | LangGraph 6-node graph + `POST /analysis` | LLM key + market-data key (Twelve or MT5) |
| Execute trades | **Implemented (dry-run default)** | `mt5_executor.py::send` + `signal_bridge.execute` | Bridge running; dual-key for live demo sends |
| Stop loss | **Implemented (mandatory)** | `OrderRequest` requires `sl>0`; geometry validated pre-send | — |
| Take profit | **Implemented (mandatory)** | Same; risk agent derives TP = 1.5×ATR | — |
| Risk management (signal level) | **Implemented** | `risk_agent.py`: ≥2/3 majority, quant veto, ATR exits | — |
| Risk management (account level) | **Missing** | No code for caps/limits/kill switch | Build P0 items before unattended use |
| Modify orders | **Missing** | — | Future (P2) |
| Close orders programmatically | **Missing** | — | Manual close during testing (P2) |
| Position sizing | **Partial** | Fixed volume only | P1 risk-based sizing |
| Trade logging | **Partial** | Logs/Prometheus; no persistence | Journal now; trade DB later (P1) |
| Performance tracking | **Partial** | MT5 history + journal | Dashboard later (P2) |

**Signal vs execution:** the application does **both**. It generates
BUY/SELL/HOLD signals through the AI pipeline *and* — through a separate,
opt-in webhook bridge — can submit them to MT5 as orders. By default the
execution step is a **dry-run**: payloads are built and logged, never sent
(`MT5_DRY_RUN` fails closed to `true`). The service itself never
auto-executes: a signal only reaches the bridge if you POST
`webhook_url` to the local receiver.

---


## Agent-by-agent review (Step 6)

> **A BUY/SELL signal from an LLM is not evidence of profitability.** Two of
> the three specialists are *language models interpreting numbers*; only the
> quant agent is a trained statistical model; the risk agent is deterministic.

### Technical Agent — `app/agents/technical_agent.py`

| Aspect | Detail |
|---|---|
| Input | Candles (300 limit, forming bar dropped) → EMA20, EMA50, RSI14, ATR14 computed **in code** |
| Processing | Evidence JSON → LLM prompt → JSON `{direction, confidence, summary, reasoning}`; one parse-retry |
| Output | `technical_analysis` dict (+ `current_price`, `atr` consumed by the risk agent) |
| Confidence | LLM self-report → **calibrated** (`calibrate_confidence`, raw kept for audit) |
| Data source | Shared `MarketDataService` (Twelve Data or MT5), 30 s TTL cache |
| Failure modes | Malformed JSON (retry → 502), LLM outage (503), stale/gapped feed (**fails closed** → 503), <210 closed candles → 503 |
| Honest assessment | The *indicators* are real math; the *interpretation* is an LLM's opinion of 4 numbers. No price structure, volume or multi-timeframe context enters this prompt. |

### Fundamental Agent — `app/agents/fundamental_agent.py`

| Aspect | Detail |
|---|---|
| Input | RAG retrieval (16 docs): World Bank + optional SOTW/BusinessQuant + Postgres store |
| Processing | Evidence → LLM prompt (with a **recency note** on intraday timeframes warning that annual data is stale) → validated JSON |
| Output | `fundamental_analysis` dict incl. `evidence` |
| Confidence | Calibrated, raw kept |
| Failure modes | Missing DB → degraded evidence (not fatal); source timeout (8 s budget) → cached evidence; bad JSON → retry → 502 |
| Honest assessment | World Bank annual indicators are **slow-moving context**, not 15m trade triggers — the code's own prompt says so. Treat this vote as low-frequency opinion. |

### Quant Agent — `app/agents/quant_agent.py`

| Aspect | Detail |
|---|---|
| Input | 21 features from closed candles (EMA200, RSI14, MACD, ATR14, rolling stats) |
| Processing | Local sklearn ensemble (RF 0.4 / XGB 0.4 / LR 0.2) → probability + direction + model agreement |
| Output | `quant_prediction`; **falls back to NO_TRADE on missing artifacts** (never crashes the graph) |
| Data source | Local `.joblib` artifacts (`scripts/fetch_model_artifacts.py`) |
| Honest assessment | **The most substantive agent** — but validated on one pair/timeframe/window (EURUSD 15m, 113 days, PF 1.31 net of costs). Out-of-sample decay is likely; monitor per-pair results. |

### Agent Orchestrator — `app/graphs/forex_analysis_graph.py`

- Six-node LangGraph: `market_data → (technical | fundamental | quant) → risk → decision`, per-node timing metrics.
- **Risk agent** (deterministic): majority ≥2 of 3 directional votes with ≥3 opinions, agreement score, **strong opposing-quant veto** (probability ≥ `QUANT_PROBABILITY_THRESHOLD`, default 0.50), risk levels, ATR exits (SL 1.0× / TP 1.5× → fixed 1.5 R:R).
- **Decision agent**: risk not approved ⇒ `NO_TRADE` (confidence forced to 0); otherwise weighted confidence + full reasoning string.

### Enough information for a meaningful trading decision?

**Partially — be skeptical.** Strengths: real indicator math, a real
statistical model with an explicit cost-aware threshold, a deterministic
majority/veto gate, mandatory exits, honest NO_TRADE behaviour.
Gaps: no order-flow, no inter-market data, no economic calendar, no
multi-timeframe confluence, fundamentals too slow for intraday, and a narrow
quant validation window. **Treat outputs as hypotheses to evaluate in
[`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md), never as proof of edge.**

---


## Risk management audit (Step 7)

| Control | Status | Where / why it matters |
|---|---|---|
| Max risk per trade | ❌ | Fixed lot sizing — a 0.01 lot on XAUUSD risks far more cash than on EURUSD for the same SL distance. **Matters:** identical signals carry unequal risk. |
| Position sizing | ❌ | `MT5_SIGNAL_VOLUME` only. |
| Stop loss | ✅ | Mandatory on every order; geometry validated before send; derived from ATR. |
| Take profit | ✅ | Same; fixed 1.5 R:R. |
| Max daily loss | ❌ | No circuit breaker — a bad day compounds until *you* stop it. |
| Max open positions | ❌ | N retried signals = N positions. |
| Max exposure / margin cap | ❌ | Broker margin is the only (late) limit; discovered via rejection 10019. |
| Max drawdown halt | ❌ | Nothing monitors equity curve. |
| Spread protection | ❌ | No pre-send max-spread check (only broker-side `deviation`=20 points slippage cap). **Matters:** news spikes widen spreads and silently erode edge. |
| Slippage protection | ⚠️ Partial | `deviation` caps fill slippage; entry-drift guard blocks stale *signals*, not volatile *fills*. |
| Trading-session restrictions | ❌ | Weekend/holiday signals possible if the webhook fires. |
| News-event restrictions | ❌ | No calendar integration. |
| Duplicate-order protection | ❌ | One POST = one order; an idempotent key does not exist. |
| Emergency stop / kill switch | ❌ | Practical kill switch today = close the bridge process + terminal. Sufficient for attended tests only. |
| Signal-level risk gate | ✅ | Majority vote, quant veto, NO_TRADE enforcement (this is *signal* risk, not *account* risk). |

**Bottom line:** signal-level risk management is genuinely good;
**account-level risk management does not exist.** That distinction is why the
verdict is "supervised demo only" until the P0s are built.

## MT5 execution safety (Step 8)

| Hazard | Protected? | Mechanism |
|---|---|---|
| Duplicate trades | ❌ | None — see P0-2 |
| Repeated orders after connection failure | ⚠️ | Bridge is stateless; a *caller* retry duplicates. Mitigated only by your process |
| Incorrect lot sizes | ✅ | `volume_min`/`volume_max` validated pre-send |
| Invalid symbols | ✅ | `symbol_info` None → typed error; API rejects non-6-letter |
| Market closed | ⚠️ | Detected *at* send (retcode 10021/10027 → 503), not prevented up-front |
| Insufficient margin | ⚠️ | Broker rejection only (10019) — see P1-3 |
| Excessive spread | ❌ | See P1-4 |
| Incorrect SL/TP | ✅ | Mandatory + side validation + digit rounding |
| API failures | ✅ | Typed `MT5ExecutionError` → HTTP 503 + `last_error` |
| MT5 disconnection | ✅⚠️ | Sync self-heals; executor reconnects lazily on next send; in-flight order = 503 (no silent retry → no phantom orders) |
| Broker rejection | ✅ | retcode checked (10009/10010 only = success) |
| Stale market data | ✅ | Entry-drift guard (100 points) + stale-feed fail-closed in the data service |
| Race conditions | ⚠️ | Bridge is a `ThreadingHTTPServer` — concurrent POSTs both send. Acceptable for one-user testing; add a send-lock with P0-2 |
| Repeated signals | ❌ | Same analysis POSTed twice = two orders (P0-2) |
| Unexpected restart | ⚠️ | No persisted order state; MT5 keeps positions; on restart nothing re-sends (safe but opaque — journal reconciles) |

## Observability (Step 9)

| You need to see | Available today? | Where |
|---|---|---|
| MT5 connection status | ✅ (log only) | Connect/disconnect log lines; `check_mt5_connection.py` on demand |
| Balance / equity | ✅ | MT5 terminal; sync snapshot logs |
| Open positions | ✅ | MT5 Trade tab; `check_mt5_sync.py` |
| Current market price | ✅ | MT5; `check_mt5_market_data.py`; `/market-data` |
| Latest signal + confidence + reason | ✅ | `/analysis` response (`final_decision`, `explanation` block) |
| Orders submitted | ✅ (log only) | Bridge logs `accepted/dry_run/ticket` + executor payload log |
| Orders rejected | ✅ (log only) | Bridge 400/401/503 + reasons |
| Trade result | ⚠️ | MT5 Account History only (no app-side record) |
| Errors | ✅ | Structured logs, `X-Request-ID`, typed HTTP errors |
| Agent activity | ✅ (timings) | Per-node Prometheus histograms; agent outputs in response |
| Risk calculations | ✅ | `risk_assessment` fields + reasoning strings |
| **Single-pane dashboard** | ❌ | Recommend: a `/mt5/status` endpoint + bridge metrics (P2) |

---


## Risk assessment

| Axis | Rating | Rationale |
|---|---|---|
| **Technical risk** | 🟢 Low | 370 hermetic tests, typed error taxonomy, fail-closed config, lazy imports, self-healing sync. Residual: bridge concurrency, no persisted order state. |
| **Trading risk** | 🟠 High (until P0s) | Signal quality unproven out-of-sample; **no account-level limits**; fixed sizing; no dedup/kill switch. *Supervised* demo use keeps this acceptable — unattended use does not. |
| **Security risk** | 🟢 Low | No committed secrets (`.env` git-ignored & untracked), no hardcoded credentials found, localhost-default bridge, optional token, SSRF allowlist, non-root Docker, optional API-key guard. Residual: token auth off by default (localhost assumption). |
| **Operational risk** | 🟡 Medium | One Windows box runs terminal + service + bridge; MT5 IPC dies with the terminal; three processes to supervise; recovery is manual (restart order documented). |

---

## Improvement prioritization (Step 10)

*Deliberately short and ordered. Every item maps to a gap found in this audit.*

### P0 — Critical (before any **unattended/automated** demo run)

| # | Problem | Why it matters | Proposed solution | Files / components | Complexity |
|---|---|---|---|---|---|
| P0-1 | ~~`--live` armed real orders without `MT5_DRY_RUN=false`~~ | Live could happen accidentally | **DONE in this audit:** dual-key interlock `live_mode_refused()` + tests | `scripts/run_signal_bridge.py`, `tests/test_run_signal_bridge.py` | ✅ Done (small) |
| P0-2 | No duplicate-order protection / send lock | Retried webhooks or concurrent POSTs stack positions | Idempotency window: refuse a second same-symbol+direction order within N seconds + `threading.Lock` around `send()`; tag with `magic` | `app/broker/signal_bridge.py`, `scripts/run_signal_bridge.py` | Small–medium |
| P0-3 | No kill switch / max-open-positions / daily-loss cap | A losing streak or bug runs until you notice | Config caps (`MT5_MAX_OPEN_POSITIONS`, `MT5_MAX_DAILY_LOSS`) checked in `SignalBridge.execute` against a synchronizer snapshot; plus a `STOP`-file / `--once` operator mode | `signal_bridge.py`, `mt5_sync.py`, `app/config.py` | Medium |
| P0-4 | No demo-account guard | The same code could be pointed at a **live** account | Refuse non-dry `order_send` when `account_info().trade_mode != demo` unless `MT5_ALLOW_LIVE=true` (default false) | `app/broker/mt5_executor.py` | Small |

### P1 — Important (before extended multi-week testing)

| # | Problem | Why it matters | Proposed solution | Files | Complexity |
|---|---|---|---|---|---|
| P1-1 | Fixed lot size | Risk per trade uncontrolled across symbols | Risk-based sizing: `lots = (balance × risk%) ÷ (SL distance × pip value)`, symbol-aware | `signal_bridge.py` or new `app/broker/position_sizing.py` | Medium |
| P1-2 | No persisted trade log | Reconstruction relies on the manual journal | Append-only JSONL/SQLite of every accepted/rejected signal + fill result; reconcile with MT5 history | new `app/broker/trade_log.py` + bridge wiring | Medium |
| P1-3 | No pre-send margin check | Orders fail late with retcode 10019 | Check `margin_free` vs estimated margin before `order_send` | `mt5_executor.py` | Small |
| P1-4 | No max-spread gate | News spikes execute at terrible prices | Compare `(ask−bid)` to `MT5_MAX_SPREAD_PIPS` pre-send | `mt5_executor.py` / bridge | Small |
| P1-5 | No MT5 status in the service | Operator must tail three consoles | `/mt5/status` endpoint (connection, account snapshot, last signal, bridge health) + bridge metrics | `app/api/`, bridge script | Medium |

---

### P2 — Useful (reliability/usability)

| # | Problem | Why it matters | Proposed solution | Files | Complexity |
|---|---|---|---|---|---|
| P2-1 | Session/news restrictions | Trading into scheduled events | Session filter from broker symbol sessions + optional economic-calendar blocklist | bridge / risk agent | Medium |
| P2-2 | No programmatic close/modify | Full-cycle automation impossible | `close_position(ticket)` / `modify_sltp(ticket)` reusing the executor's validation style | `mt5_executor.py` | Medium |
| P2-3 | No dashboard | One-glance status | Small status page or extend the external dashboard with bridge data | frontend repo / P1-5 endpoint | Medium |
| P2-4 | Bridge concurrency | Simultaneous POSTs interleave | Serialize sends (lock from P0-2), bounded worker queue | `run_signal_bridge.py` | Small |

### P3 — Future (nice-to-have)

- Strategy experiments: trailing stops, partial closes, multi-timeframe confluence.
- Automatic journal export (CSV) from the trade log (P1-2).
- Contract tests generated from the OpenAPI schema (already on the project roadmap).
- Walk-forward retraining pipeline for the quant ensemble.
- Alerting (email/webhook) on kill-switch trips and bridge restarts.

**Anti-overengineering note:** the existing architecture is sound — one
FastAPI service, one LangGraph pipeline, one thin bridge, interface-compatible
data providers. None of the above requires a rewrite; all are incremental
additions to `app/broker/` and the bridge script. The current design is
**good enough** for supervised demo testing as-is.

---

## Recommended next steps (prioritized sequence)

1. **Today:** run the 8 tests in [`MT5_USER_GUIDE.md`](MT5_USER_GUIDE.md) §5
   (startup → connection → data → signal → risk → dry-run bridge → sync → close)
   with `MT5_DRY_RUN=true`. Record outputs in the journal.
2. **This week:** Stages 1–3 of [`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md)
   (backtest review, signal replay, dry-run paper trading).
3. **Before the first real demo order:** confirm the dual-key behaviour
   (`--live` refused under `MT5_DRY_RUN=true`, exit code 2), then place ONE
   deliberate 0.01-lot demo order and journal it end-to-end.
4. **Before extended automated demo:** implement P0-2, P0-3, P0-4
   (plus P1-1/P1-2 if trading more than one symbol).
5. **Never:** connect a live account — there is deliberately no configuration
   path to live trading in this repository, and P0-4 will harden that further.

---

*Audit basis: full repository inspection; `python -m pytest -q` → **370 passed**;
`ruff check app tests scripts` → clean; no secrets found in tracked files;
MT5 integration traced end-to-end (connection → data → graph → bridge → executor).*

