# ForexAI — MT5 Quick Start

> **Shortest safe path from nothing to your first evaluated signal.**
> Estimated time: 45–90 minutes (excluding MT5 download).
> **This procedure uses a DEMO account only. Never use a live account for testing.**

All commands are run from the repository root (`c:\Users\mcngc\Downloads\ForexAi\forexai-ai`)
in PowerShell, unless stated otherwise.

---

## 1. Install MT5

1. Download **MetaTrader 5** from your broker's website (preferred) or from
   [metatrader5.com](https://www.metatrader5.com/).
2. Run the installer. Default install path used by this project:
   `C:\Program Files\MetaTrader 5\terminal64.exe`
   (if you install elsewhere, set `MT5_PATH` in `.env`, see step 3).

## 2. Create / log into a DEMO account

1. Open MT5 → **File → Open an Account** → pick your broker → select **Demo**.
2. Choose leverage ≤ 1:100 and a balance you would be willing to lose (e.g. 10 000 USD).
3. Log in. Confirm the **Market Watch** window shows quotes that tick
   (right-click → **Show All** to display all symbols).
4. In **Tools → Options → Expert Advisors**, enable **Allow algorithmic trading**.
5. Keep the terminal **open and logged in** — ForexAI's execution bridge attaches to
   the running terminal session.

## 3. Configure ForexAI

Edit `.env` in the repo root (it already exists; it is git-ignored — never commit it).
Add/verify these lines:

```dotenv
# --- MT5 block ---
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_LOGIN=your_demo_login
MT5_PASSWORD=your_demo_password
MT5_SERVER=your_demo_server      # exact spelling as shown in MT5 login window
MT5_TIMEOUT_SECONDS=60

# Safety switch — MUST stay true for the first tests (this is the default):
MT5_DRY_RUN=true

# Optional: feed the analysis graph from MT5 instead of Twelve Data
# MARKET_DATA_PROVIDER=mt5

# Signal bridge
MT5_SIGNAL_VOLUME=0.01
BRIDGE_TOKEN=change-me-to-a-long-random-string
```

> **Credentials safety:** `.env` is excluded by `.gitignore` (`.env`, `.env.*`,
> `!.env.example`). Never paste credentials into chat, tickets, screenshots or
> shell history — prefer editing the file over `--password` command-line flags
> (flags are visible in process listings).

## 4. Start the application

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ForexAI AI Service is running", ...}`

## 5. Connect to MT5

```powershell
python scripts/check_mt5_connection.py
```

Expected: `DRY-RUN OK login=... server=... balance=... equity=... trade_allowed=True (no orders placed)`

## 6. Verify market data

```powershell
python scripts/check_mt5_market_data.py --symbol EURUSD --timeframe FiveMinutes --limit 5
```

Expected: a table of 5 UTC-stamped candles + one bid/ask tick, ending `DRY-RUN OK: no orders placed.`

If you set `MARKET_DATA_PROVIDER=mt5`, also verify the HTTP route:

```powershell
curl "http://localhost:8000/market-data/EURUSD?timeframe=FifteenMinutes&limit=10"
```

## 7. Generate your first signal

```powershell
curl -X POST http://localhost:8000/analysis -H "Content-Type: application/json" -d '{"forex_pair_id":"EURUSD","symbol":"EURUSD","timeframe":"FifteenMinutes"}'
```

Expected: HTTP 200 JSON with `technical_analysis`, `fundamental_analysis`,
`quant_prediction`, `risk_assessment` (incl. `entry_price`, `stop_loss`, `take_profit`)
and `final_decision.direction` ∈ `BUY | SELL | HOLD | NO_TRADE`.
(A `HOLD`/`NO_TRADE` result is a **valid** outcome — retry later or try another pair.)

## 8. Verify risk calculation

In the same response check `risk_assessment`:

- `stop_loss` and `take_profit` are present and on the correct sides of `entry_price`
  (BUY: SL < entry < TP; SELL: TP < entry < SL),
- `risk_reward` ≈ 1.5 (SL = 1.0×ATR, TP = 1.5×ATR — see `app/agents/risk_agent.py`),
- `approved` must be `true` for the signal to be executable at all.

## 9. Execute your first DEMO trade (optional — dry-run first)

**9a. Dry-run the bridge (default — no orders leave your machine):**

```powershell
python scripts/run_signal_bridge.py
```

Then re-run the analysis with
`"webhook_url": "http://127.0.0.1:8799/signal?token=YOUR-BRIDGE-TOKEN"` .
Expected in the bridge console: `DRY-RUN: ... NOT sent.` and HTTP response `"dry_run": true`.

**9b. One real DEMO order (requires BOTH switches — dual-key):**

1. Set `MT5_DRY_RUN=false` in `.env`.
2. Start the bridge with `--live`:

```powershell
python scripts/run_signal_bridge.py --live
```

3. Send the same webhook analysis again.

Expected: `"accepted": true, "dry_run": false, "ticket": <number>, "retcode": 10009`
and the position visible in MT5's **Trade** tab with SL/TP attached.

> If `--live` is passed while `MT5_DRY_RUN` is not explicitly `false`, the bridge
> **refuses to start** (safety interlock). That is intended behaviour.

## 10. Monitor the result

- MT5 → **Trade** tab: position, floating P/L, SL/TP.
- ForexAI logs (uvicorn console): analysis and webhook delivery.
- Bridge console: every accepted/rejected signal.
- Record everything in [`docs/MT5_TRADE_JOURNAL.md`](MT5_TRADE_JOURNAL.md).

## 11. Record the result

Add a journal row (date, symbol, signal, confidence, entry, SL, TP, exit, P/L,
reasons, market conditions). No trade is complete until it is journaled.

## 12. Stop the system safely

1. Close open demo positions in MT5 (or let SL/TP run — your choice, but journal it).
2. Press `Ctrl+C` in the bridge terminal → `Signal bridge stopping.`
3. Press `Ctrl+C` in the uvicorn terminal.
4. Set `MT5_DRY_RUN=true` again in `.env` before the next session.
5. ForexAI never runs unattended — close MT5 when you are done.

---

## What just happened

| Step | Component | Real contact with broker? |
|---|---|---|
| 4 | FastAPI service (`app/main.py`) | No |
| 5–6 | `app/broker/mt5_connection.py`, `mt5_market_data_provider.py` | Read-only IPC |
| 7–8 | LangGraph pipeline (`app/graphs/forex_analysis_graph.py`) | No |
| 9 | `scripts/run_signal_bridge.py` → `app/broker/signal_bridge.py` → `mt5_executor.py` | Dry-run unless dual-key live |

**Next:** [`MT5_USER_GUIDE.md`](MT5_USER_GUIDE.md) for the full explanation ·
[`MT5_TESTING_PLAN.md`](MT5_TESTING_PLAN.md) before risking even demo capital ·
[`MT5_TROUBLESHOOTING.md`](MT5_TROUBLESHOOTING.md) if anything fails.
