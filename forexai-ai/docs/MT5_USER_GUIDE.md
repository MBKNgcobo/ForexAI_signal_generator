# ForexAI — MT5 Setup & User Guide

> **Audience:** a technically capable user who wants to test the ForexAI signal
> system against **their own MetaTrader 5 installation and a DEMO account**.
> **This guide never applies to live accounts.** Everything below is grounded in
> the actual code of this repository; where something does not exist, the guide
> says so explicitly instead of pretending it does.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [MT5 installation](#2-mt5-installation)
3. [Connecting ForexAI to MT5](#3-connecting-forexiai-to-mt5)
4. [Recommended safe testing architecture](#4-recommended-safe-testing-architecture)
5. [First-time test procedure](#5-first-time-test-procedure)

---

## 1. Prerequisites

### 1.1 Windows requirements

The MT5 integration is **Windows-only**. The `MetaTrader5` Python package talks to
the terminal over local IPC and does not exist for Linux/macOS; this project pins it
with a platform marker in `requirements.txt`:

```text
MetaTrader5==5.0.6231; sys_platform == 'win32'
```

| Requirement | Detail |
|---|---|
| OS | Windows 10/11 (the machine running `terminal64.exe` must run ForexAI too) |
| MT5 terminal | Installed and logged into a **demo** account |
| Python | 3.14 (project target; current `.venv` is 3.14.2) |
| Virtualenv | `.venv` already exists in the repo root |
| Ports | `8000` (ForexAI API), `8799` (signal bridge), plus the MT5 terminal process |
| Services | The MT5 terminal must be **open and logged in** before the bridge starts (bridge uses *attach mode*) |

> **Docker:** the Dockerfile builds a Linux image. It can run the *analysis*
> service, but it can **never** talk to MT5. Run MT5 components natively on Windows.

### 1.2 Python packages

Runtime dependencies live in `requirements.txt` (FastAPI, LangGraph, pandas,
scikit-learn, xgboost, `MetaTrader5`, …). Dev tools in `requirements-dev.txt`
(`ruff`, `pytest-cov`). Install:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

Verify the MT5 package:

```powershell
python -c "import MetaTrader5; print(MetaTrader5.__version__)"
```

Expected: `5.0.6231` (or newer). If it fails, see
[`MT5_TROUBLESHOOTING.md`](MT5_TROUBLESHOOTING.md).

### 1.3 Broker / account requirements

- A **DEMO** account with a broker that offers MT5. Demo is not optional —
  it is required for every phase of [`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md).
- Recommended: balance ≥ 10 000 units, leverage ≤ 1:100, symbols enabled:
  at minimum **EURUSD**, ideally also **XAUUSD / USDJPY / GBPUSD** for
  multi-pair testing.
- You need three values from the login window: **Login** (numeric account
  number), **Password** (demo), **Server** (exact broker server name).

### 1.4 Required environment variables

All configuration lives in `.env` at the repo root (never in code, never committed).

| Variable | Required for | Default | Purpose |
|---|---|---|---|
| `MT5_PATH` | All MT5 components | `C:\Program Files\MetaTrader 5\terminal64.exe` | Path to `terminal64.exe` (auto-launched if not running) |
| `MT5_LOGIN` | Credential mode / `MARKET_DATA_PROVIDER=mt5` | — | Demo account number |
| `MT5_PASSWORD` | Credential mode | — | Demo password |
| `MT5_SERVER` | Credential mode | — | Broker server name |
| `MT5_TIMEOUT_SECONDS` | Connection | `60` | IPC/init timeout |
| `MT5_DRY_RUN` | Execution | **`true`** | **Master safety switch:** `true` = build & log payloads, never send |
| `MT5_SIGNAL_VOLUME` | Signal bridge | `0.01` | Fixed lot per signal (no automatic position sizing exists) |
| `BRIDGE_TOKEN` | Bridge auth | unset (off, localhost only) | Shared secret required as `?token=` on `/signal` |
| `MARKET_DATA_PROVIDER` | Graph data source | `twelve` | `twelve` (cloud API) or `mt5` (local terminal) |

Optional: `WEBHOOK_ALLOWLIST` (localhost always allowed), `AI_SERVICE_API_KEY`
(API guard), `LOG_LEVEL` / `LOG_FORMAT`.

### 1.5 Storing credentials safely

1. Keep them **only** in `.env` — ignored by `.gitignore` (`.env`, `.env.*`,
   `!.env.example`) and `.dockerignore`. Verify with `git ls-files .env`
   → must return nothing.
2. Prefer `.env` over `--password` command-line flags (process arguments are
   visible to other local processes).
3. Never commit, screenshot, paste or log the values. The app never prints them:
   `check_mt5_connection.py` logs balances only; startup logs print variable
   *names*, not values.
4. Use a **demo-only** password; treat even demo credentials as sensitive.
5. If a credential leaks, change it in MT5 account settings immediately.

---

## 2. MT5 installation

Step-by-step, in order. Do not skip the verification steps.

### Step 1 — Install MT5

1. Prefer the installer provided by **your broker** (it pre-configures the demo
   server). Otherwise use the official MetaQuotes installer.
2. Accept the defaults. The default path (`C:\Program Files\MetaTrader 5\terminal64.exe`)
   matches `DEFAULT_TERMINAL_PATH` in `app/broker/mt5_connection.py`, so no
   configuration is needed if you accept it.

### Step 2 — Log into a DEMO account

1. Launch MT5 → **File → Open an Account** → select your broker → **Demo account**.
2. Record the **login**, **password** and **server** name for `.env` (§1.4).
3. Confirm the account appears in the bottom-right corner and the toolbar shows
   a green **Algo Trading** button (enabled).

### Step 3 — Confirm the terminal is running

- The `terminal64.exe` process must be visible in Task Manager.
- ForexAI can also launch it: `ensure_terminal_running()` in
  `app/broker/mt5_connection.py` starts `MT5_PATH` when no `terminal64.exe`
  process is found, then waits up to the timeout.

### Step 4 — Confirm the desired symbols are available

1. **Market Watch → right-click → Show All**.
2. Find your test symbols (EURUSD, XAUUSD, USDJPY…). If your broker uses
   suffixes (`EURUSD.m`, `EURUSD+`) **this is handled automatically**:
   `MT5MarketDataProvider._resolve_symbol()` resolves broker suffixes internally —
   you always request the plain name (`EURUSD`).
3. If a symbol is missing entirely, right-click → **Symbols** → add it. A symbol
   MT5 does not know cannot be analysed or traded.

### Step 5 — Confirm market data is updating

- Select a symbol in Market Watch; bid/ask must tick during market hours.
- Verify programmatically with
  `python scripts/check_mt5_market_data.py --symbol EURUSD` (Test 3 below).
- Outside market hours ticks stop — see troubleshooting.

### Step 6 — AutoTrading settings

- Enable **Tools → Options → Expert Advisors → Allow algorithmic trading**.
- This project does **not** install an Expert Advisor; it uses the official
  Python `MetaTrader5` API. Enabling algorithmic trading still matters because
  brokers may reject non-manual orders otherwise (`trade_allowed` is checked on
  connect and logged).

### Step 7 — MT5 configuration relevant to *this* application

| Setting | Why it matters | Where |
|---|---|---|
| Terminal **open & logged in** (attach mode) | The signal bridge connects **without credentials** — it reuses the open terminal session | MT5 main window |
| Algo Trading enabled + `trade_allowed=True` | Orders may otherwise be rejected | MT5 toolbar / account |
| Symbols visible & ticking | Market data + order pricing | Market Watch |
| **Demo** account | Every phase of this guide assumes demo | Account login |
| Same machine as ForexAI | IPC is local-only | — |

> No other MT5 settings are required. There is no EA to attach, no DLL to
> allow, no chart to open.

---

## 3. Connecting ForexAI to MT5

**Verdict: the current application DOES provide an MT5 integration.** It is
implemented in `app/broker/` and exercised by dedicated scripts and tests
(`tests/test_mt5_connection.py`, `test_mt5_market_data.py`, `test_mt5_orders.py`,
`test_mt5_sync.py`, `test_signal_bridge.py` — hermetic fakes in CI, real IPC
on your machine). How each piece connects:

### 3.1 The two connection modes

`app/broker/mt5_connection.py → connect()` supports:

| Mode | When | Credentials | Used by |
|---|---|---|---|
| **Attach** (`login=None`) | Terminal already open & logged in | None needed | Signal bridge, `check_mt5_orders.py`, `check_mt5_sync.py`, `check_mt5_market_data.py` (without flags) |
| **Credential login** | Unattended / service use | `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` | `check_mt5_connection.py`, `MT5MarketDataProvider` when `MARKET_DATA_PROVIDER=mt5` |

Failures raise `MT5ConnectionError` with `mt5.last_error()` attached. On connect
the code logs: login, server, balance, currency, equity, `trade_allowed` —
never the password.

### 3.2 Component-by-component

#### (a) Connection layer — `app/broker/mt5_connection.py` — **Implemented**

- `ensure_terminal_running()` verifies `MT5_PATH` exists; launches
  `terminal64.exe` if no such process is running; waits for it to appear.
- `connect(...)` → `mt5.initialize(...)` (+ `mt5.login(...)` in credential mode)
  → `mt5.account_info()` → `MT5AccountInfo` snapshot.
- `shutdown()` releases the IPC handle (safe when never connected).
- `_import_mt5()` is lazy: the service starts and tests run on any OS; only an
  actual MT5 call requires Windows + the package.

#### (b) Market data — `app/broker/mt5_market_data_provider.py` — **Implemented**

- Implements the same `MarketDataProvider` interface as the Twelve Data provider,
  so the LangGraph agents are **identical** whichever source is configured.
- Selected by `MARKET_DATA_PROVIDER=mt5` in
  `app/services/market_data_provider_factory.py` (validates `MT5_LOGIN`,
  numeric login, timeout — errors map to HTTP 503, not 500).
- `get_market_data()` maps `OneMinute…OneDay` → MT5 `TIMEFRAME_M1…D1`,
  fetches via `copy_rates_from_pos`, converts broker-clock epochs to **UTC**,
  de-duplicates forming candles, returns the frozen `Candle` schema.
- Extras: `get_tick()` (bid/ask), `get_depth()` (order book).
- Broker suffixes (`EURUSD.m`) are resolved internally.

#### (c) Account & position sync — `app/broker/mt5_sync.py` — **Implemented (read-only)**

- `MT5StateSynchronizer.snapshot()` pulls `account_info` + `positions_get` +
  `orders_get` into immutable dataclasses (`AccountSnapshot` includes balance,
  equity, margin, margin_free, `trade_allowed`).
- `poll_once()` diffs snapshots → `SyncReport` (opened/closed/modified positions
  & orders, balance/equity deltas).
- `start_background()` polls every 2 s in a daemon thread; failures log a
  warning and reconnect on the next tick.
- **It never sends orders.** Closing/modifying positions is manual (MT5 UI).

---

#### (d) Order execution — `app/broker/mt5_executor.py` — **Implemented, DRY-RUN by default**

- `OrderRequest` **requires** `sl > 0`, `tp > 0`, `sl ≠ tp`, `volume > 0`;
  limit/stop require `price`. Invalid → `ValueError` (never reaches the terminal).
- `build_payload()` resolves the broker symbol, fetches `symbol_info` + tick,
  validates **SL/TP bracket the fill price on the correct sides**
  (BUY: `sl < price < tp`; SELL: `tp < price < sl`), enforces
  `volume_min`/`volume_max`, picks the broker's filling mode (FOK/IOC/RETURN)
  and rounds prices to symbol digits.
- `send()`: dry-run logs the exact payload and returns `OrderResult(dry_run=True)`
  **without calling `order_send`**. Live mode raises `MT5ExecutionError` unless
  the broker returns retcode `10009`/`10010`.
- Dry-run precedence: explicit argument > executor setting > `MT5_DRY_RUN`
  config. **Any unset/garbage `MT5_DRY_RUN` resolves to dry-run.**

#### (e) Signal bridge — `app/broker/signal_bridge.py` + `scripts/run_signal_bridge.py` — **Implemented**

This is the piece that turns *signals* into *orders*:

```text
POST /analysis (webhook_url) → AiAnalysisResponse JSON
    → SignalBridge gates (pure, unit-tested):
        - direction must be BUY/SELL (HOLD / NO_TRADE rejected → 400)
        - risk_assessment.approved must be true
        - stop_loss / take_profit / entry_price must exist
        - optional min-confidence gate
        - entry-drift guard: market price may not have moved
          > 100 points (10 pips on a 5-digit broker) from entry_price
        - optional ?token= auth (BRIDGE_TOKEN, constant-time compare)
    → OrderRequest (market order, mandatory SL/TP, fixed volume)
    → MT5TradeExecutor.send()  (dry-run unless dual-key live)
```

Start it on the Windows machine that hosts MT5:

```powershell
python scripts/run_signal_bridge.py               # DRY-RUN (default)
python scripts/run_signal_bridge.py --live        # also requires MT5_DRY_RUN=false
```

Endpoints: `GET /health` → `{"ok": true}`;
`POST /signal?token=...` → `200 accepted | 400 rejected | 401 bad token |
503 terminal failure`. Binds `127.0.0.1:8799` by default — never expose the port.

### 3.3 Configuration summary

```dotenv
# .env — analysis service
MARKET_DATA_PROVIDER=mt5        # optional; 'twelve' works too
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=...
MT5_TIMEOUT_SECONDS=60
MT5_DRY_RUN=true                # keep true until your first deliberate demo order

# .env — signal bridge
MT5_SIGNAL_VOLUME=0.01
BRIDGE_TOKEN=<long random value>
```

### 3.4 How to start everything (exact commands)

```powershell
# Terminal 1 — analysis service
cd c:\Users\mcngc\Downloads\ForexAi\forexai-ai
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --port 8000

# Terminal 2 — verification scripts (any time, read-only / dry-run)
python scripts/check_mt5_connection.py
python scripts/check_mt5_market_data.py --symbol EURUSD
python scripts/check_mt5_sync.py --count 3

# Terminal 3 — signal bridge (when you want signals to reach MT5)
python scripts/run_signal_bridge.py
```

---

## 4. Recommended safe testing architecture

```text
        MT5 DEMO Account  (your terminal, open & logged in)
                ↓ read-only IPC
            ForexAI
                ↓
          Market Data      (MT5 provider or Twelve Data)
                ↓
     AI / Technical / Fundamental / Quant Agents   (LangGraph)
                ↓
            Signal          (BUY / SELL / HOLD + confidence + reasoning)
                ↓
        Risk Management     (majority vote, quant veto, ATR SL/TP, approval gate)
                ↓
        Trade Decision      (final direction or NO_TRADE)
                ↓ webhook (localhost:8799, token)
      Signal Bridge gates   (HOLD/approved/SL-TP/drift/token checks)
                ↓
      MT5 Demo Execution    (DRY-RUN by default → dual-key live)
                ↓
         Trade Logging      (structured logs + Prometheus + manual journal)
                ↓
     Performance Dashboard  (MT5 terminal + your journal — see gaps below)
```

### What exists today vs what still needs building

| Stage | Status | Evidence |
|---|---|---|
| MT5 demo account interface | ✅ Exists (external) | Your MT5 installation |
| ForexAI service | ✅ Exists | `app/main.py`, 366 tests passing |
| Market data (MT5 or cloud) | ✅ Exists | `mt5_market_data_provider.py`, `market_data_provider_factory.py` |
| Technical / Fundamental / Quant agents | ✅ Exists | `app/agents/*`, LangGraph `forex_analysis_graph.py` |
| Signal generation + explanation | ✅ Exists | `AiAnalysisResponse` + `explanation` block |
| Risk gate (signal level) | ✅ Exists | `app/agents/risk_agent.py` (majority, veto, ATR exits) |
| Trade decision | ✅ Exists | `app/agents/decision_agent.py` (`NO_TRADE` on failed risk) |
| Bridge gates + execution | ✅ Exists (dry-run default) | `signal_bridge.py`, `mt5_executor.py` |
| Trade logging (automated, persisted) | ⚠️ Partial — logs only | uvicorn/bridge consoles, Prometheus `/metrics`; **no trade DB** |
| Performance dashboard | ❌ Not built | Use MT5 **Account History** + [`MT5_TRADE_JOURNAL.md`](MT5_TRADE_JOURNAL.md) |
| Position sizing by risk % | ❌ Not built | Fixed `MT5_SIGNAL_VOLUME` (0.01) |
| Account-level limits (daily loss, max positions, kill switch) | ❌ Not built | See readiness report P0 list |
| Duplicate-signal protection | ❌ Not built | One webhook POST = one order |
| Auto close/modify positions | ❌ Not built | Manual in MT5; sync is read-only |

**Practical consequence:** for your personal evaluation you do **not** need the
missing pieces on day one — the MT5 terminal itself is the dashboard (balance,
equity, positions, history), and the manual journal is the trade log. The missing
P0 items become mandatory only before you let the system run *unattended* in
extended demo testing (see [`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md)).

---

## 5. First-time test procedure

Run the tests **in order**; each builds on the previous one. All are safe:
none sends an order unless explicitly noted.

### Test 1 — Application startup

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --port 8000
```

**Expected result:** console shows `Configuration OK (LLM provider: …)`
(or a clear list of missing variables), then
`Uvicorn running on http://127.0.0.1:8000`. `GET /health` returns 200.

**Troubleshooting:** port busy → change `--port`; import errors →
`pip install -r requirements.txt`; missing-config errors → §1.4 table +
[`MT5_TROUBLESHOOTING.md`](MT5_TROUBLESHOOTING.md).

### Test 2 — MT5 connection

```powershell
python scripts/check_mt5_connection.py
```

**Expected result:** `DRY-RUN OK login=… balance=… equity=… trade_allowed=True
(no orders placed)`, exit code 0.

**Troubleshooting:** `MT5 terminal not found` → fix `MT5_PATH`;
`login rejected` → check demo credentials/server spelling;
`no active trading session` → log into the terminal first (attach mode);
`package not installed` → `pip install MetaTrader5` (Windows only).

### Test 3 — Market data

```powershell
python scripts/check_mt5_market_data.py --symbol EURUSD --timeframe FiveMinutes --limit 5
```

**Expected result:** 5 candles with UTC timestamps + a bid/ask tick;
`DRY-RUN OK: no orders placed.` Empty candles usually mean the market is
closed — retry during session hours or try another symbol.

**Optional:** `curl "http://localhost:8000/market-data/EURUSD?limit=10"`
returns JSON candle data (uses `MARKET_DATA_PROVIDER`, default Twelve Data).

### Test 4 — Signal generation

```powershell
curl -X POST http://localhost:8000/analysis -H "Content-Type: application/json" -d '{"forex_pair_id":"EURUSD","symbol":"EURUSD","timeframe":"FifteenMinutes"}'
```

**Expected result:** HTTP 200 with all five blocks
(`technical_analysis`, `fundamental_analysis`, `quant_prediction`,
`risk_assessment`, `final_decision`). Direction may legitimately be
`HOLD`/`NO_TRADE` — that is a successful *test*, not a failure.

**Troubleshooting:** `503` → missing LLM key or market-data key (read the
detail); `502` → LLM output unparseable, retry; `422` → symbol must be six
letters, timeframe must be one of the six valid names.

### Test 5 — Risk calculation

From the Test 4 response verify `risk_assessment`:

| Field | Expected |
|---|---|
| `stop_loss`, `take_profit` | Present, non-null (when `approved`) |
| BUY geometry | `stop_loss < entry_price < take_profit` |
| SELL geometry | `take_profit < entry_price < stop_loss` |
| `risk_reward` | ≈ `1.5` (TP 1.5×ATR / SL 1.0×ATR) |
| `approved: false` | Trade correctly suppressed; `final_decision` should be `NO_TRADE` |

**Troubleshooting:** SL/TP null while `approved: true` with price/ATR > 0 should
not happen — file a bug; `approved` false with agreeing agents → read
`risk_assessment.reason` (the strong opposing quant veto is the usual cause).

### Test 6 — Demo order (dry-run first, then one live demo order)

**6a — dry-run (no order leaves your machine):**

```powershell
python scripts/run_signal_bridge.py
# in another window: POST the analysis with
#   "webhook_url": "http://127.0.0.1:8799/signal?token=YOUR-BRIDGE-TOKEN"
```

**Expected:** bridge logs `DRY-RUN: EURUSD buy market … NOT sent.`; HTTP
response `"accepted": true, "dry_run": true`.

**6b — first REAL demo order (dual-key):** set `MT5_DRY_RUN=false` in `.env`,
restart the bridge with `--live`, resend the webhook.

**Expected:** `"dry_run": false, "ticket": <n>, "retcode": 10009` and a 0.01-lot
position with SL/TP in MT5's **Trade** tab. A missing token → `401`; a missing
`--live` → dry-run. That is the safety design working.

### Test 7 — Position monitoring

The position's floating P/L updates in MT5. Optionally start the read-only
sync watcher:

```powershell
python scripts/check_mt5_sync.py --count 5 --interval 2
```

**Expected:** a snapshot each poll (balance/equity/positions/orders) and a drift
report when something changes.

### Test 8 — Trade closing

Close the position manually in MT5 (right-click → Close Position), or let its
SL/TP trigger. **Expected:** the Trade tab empties, Account History shows the
closed trade with swap/profit; record the outcome in the journal.
ForexAI does **not** auto-close positions (documented limitation).

---

