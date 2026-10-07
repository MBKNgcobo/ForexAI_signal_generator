# ForexAI — MT5 Troubleshooting Guide

> Format for every entry: **Symptoms → Likely cause → Solution → Verification**.
> Error messages quoted below are the *actual* messages this codebase produces.
> First stop for any failure: the console that produced it (uvicorn, bridge, or
> the check script) — the code always attaches `mt5.last_error()` or a typed
> reason.

---

## 1. MT5 not detected / terminal not found

- **Symptoms:** `MT5 terminal not found at: … Install MetaTrader 5 or set MT5_PATH to terminal64.exe.`
- **Cause:** MT5 installed elsewhere than `C:\Program Files\MetaTrader 5\`, or not installed.
- **Solution:** set `MT5_PATH` in `.env` to the real `terminal64.exe` path.
- **Verification:** `python scripts/check_mt5_connection.py` gets past this error.

## 2. MT5 terminal not running

- **Symptoms:** long pause then `MT5 terminal did not appear within 60s after launch …`; or in attach mode: `the terminal has no active trading session`.
- **Cause:** terminal closed; launch blocked; nobody logged in (attach mode needs a session).
- **Solution:** open MT5 manually and log in; verify `MT5_PATH`; run the terminal once yourself if Windows blocked the launch.
- **Verification:** `terminal64.exe` in Task Manager; connection check passes.

## 3. Login failure

- **Symptoms:** `MT5 login rejected for login=… server=… last_error=…`
- **Cause:** wrong password/server; live instead of demo credentials; locked account; server name misspelled (must match MT5 **exactly**).
- **Solution:** copy `MT5_SERVER` from MT5's login window; reset demo password at the broker; numeric `MT5_LOGIN`.
- **Verification:** manual login works in MT5; `check_mt5_connection.py` prints `DRY-RUN OK`.

## 4. Symbol not found

- **Symptoms:** `symbol_info returned None for …`; or HTTP `400 unsupported pair`.
- **Cause:** symbol not enabled at the broker; exotic name; disabled in Market Watch.
- **Solution:** Market Watch → Show All → enable it. Use the six-letter base name (`EURUSD`) — suffixes like `.m` are auto-resolved by `_resolve_symbol()`. API validation accepts only 6-letter alphabetic symbols.
- **Verification:** `python scripts/check_mt5_market_data.py --symbol EURUSD` prints candles.

## 5. Market closed

- **Symptoms:** stale/absent ticks; `symbol_info_tick returned None`; retcode `10027`/`10021`; candles stop advancing.
- **Cause:** weekend, holiday, broker maintenance; symbol session ended.
- **Solution:** wait for session open (check broker session times). There is **no session-time guard in the code** (documented gap) — during testing, *you* are the guard.
- **Verification:** Market Watch quotes tick; tick check returns fresh timestamps.

## 6. No price data

- **Symptoms:** `All MT5 rate rows for … were malformed`; empty candle list; `/market-data` 503.
- **Cause:** market closed (most common); symbol never quoted; cold terminal history.
- **Solution:** see #5; open a chart to force history download; try a major pair.
- **Verification:** candles appear in the check script during market hours.

## 7. Python package missing

- **Symptoms:** `The 'MetaTrader5' package is not installed. Install it on Windows with: pip install MetaTrader5. (It is Windows-only …)`
- **Cause:** fresh venv, non-Windows OS, failed install.
- **Solution (Windows):** `.venv\Scripts\Activate.ps1; pip install -r requirements.txt`
- **Verification:** `python -c "import MetaTrader5; print(MetaTrader5.__version__)"`.

## 8. Connection timeout

- **Symptoms:** `mt5.initialize returned False; the terminal is not ready. last_error=…`
- **Cause:** terminal still starting; wrong path; IPC contention; timeout too short.
- **Solution:** raise `MT5_TIMEOUT_SECONDS` (e.g. 120); let the terminal fully load before the bridge starts; restart MT5.
- **Verification:** connection check passes twice in a row.

---
## 9. Order rejected (general)

- **Symptoms:** bridge responds `503 … MT5 order rejected: retcode=… comment=…`; scripts show `Order failed: …`.
- **Cause:** read the **retcode** — `10004` requote · `10006` rejected · `10013` invalid request · `10014` invalid volume · `10015` invalid price · `10016` invalid stops · `10019` no money · `10021` market closed · `10026` disabled · `10027` autotrading disabled.
- **Solution:** fix the matching cause below. A rejected order creates **no** position — no cleanup needed; the bridge logs the failure and returns 503.
- **Verification:** next attempt returns `retcode=10009`.

## 10. Invalid volume

- **Symptoms:** `volume 0.001 below symbol minimum 0.01` (local `ValueError`) or retcode `10014`.
- **Cause:** `MT5_SIGNAL_VOLUME` outside the broker's `volume_min`/`volume_max`/step.
- **Solution:** set a volume within symbol limits (usually ≥ 0.01 in 0.01 steps). The executor checks `volume_min`/`volume_max` *before* sending.
- **Verification:** payload builds; dry-run log shows the corrected volume.

## 11. Invalid stops

- **Symptoms:** `Risk bounds invalid for buy: SL < fill price < tp …` (local `ValueError`) or retcode `10016`.
- **Cause:** SL/TP on the wrong side of price, or inside the broker's minimum stop level; price moved since the signal.
- **Solution:** this normally means a *stale or malformed signal* — the local gate catching it is the safety design working. Check the broker's `stoplevel` (via `symbol_info`); the entry-drift guard (100 points default) should reject stale entries before this.
- **Verification:** a known-good payload passes `python scripts/check_mt5_orders.py` dry-run.

## 12. Insufficient margin

- **Symptoms:** retcode `10019` ("No money"); position not opened.
- **Cause:** balance/leverage too low for the lot; other positions consuming margin.
- **Solution:** lower `MT5_SIGNAL_VOLUME`; close old positions. **Note:** the app has *no pre-send margin check* (documented gap) — pre-check `margin_free` with `python scripts/check_mt5_sync.py`.
- **Verification:** sync snapshot shows `margin_free` comfortably above the new order's requirement.

## 13. Broker restrictions

- **Symptoms:** retcode `10026`/`10027`; every order rejected on one symbol; connect log shows `trade_allowed=False`.
- **Cause:** algorithmic trading disabled (MT5 or broker side); account type blocks API trading; hedging/netting rules; symbol restricted.
- **Solution:** enable **Tools → Options → Expert Advisors → Allow algorithmic trading**; ask the broker about API/EA permissions; verify the demo account allows the direction you trade.
- **Verification:** connect log shows `trade_allowed=True`; test order passes.

---

## 14. ForexAI unable to generate a signal

- **Symptoms:** `POST /analysis` returns 500/502/503, or hangs up to 120 s.
- **Cause:** check the **status code** first: `503` = missing config / rate-limited LLM / market-data quota / timeout (detail message names the variable or dependency); `502` = the LLM produced unparseable output; `500` = internal bug (stack trace is in the uvicorn log).
- **Solution:** read the `detail` field — it is written to be actionable. For `503` run `GET /ready` which lists missing variables. For `502`, retry (agents already retry once on bad JSON).
- **Verification:** `curl /ready` → `{"status":"ready"}` and a fresh `/analysis` returns 200.

## 15. AI API unavailable (OpenRouter/OpenAI)

- **Symptoms:** `AI provider is rate-limited or unavailable. Please retry shortly.` (503), or `LLM_*` config errors at startup.
- **Cause:** missing/invalid key; provider outage; free-tier rate limits.
- **Solution:** verify `LLM_PROVIDER` + matching key vars in `.env` (names in `.env.example`); set `OPENROUTER_FALLBACK_MODELS` for resilience; wait out rate limits (`Retry-After` header).
- **Verification:** `GET /ready` clean; small `/analysis` call succeeds.

## 16. Database unavailable (fundamental RAG store)

- **Symptoms:** analysis slow or 503 mentioning the RAG store / Postgres; `connection is insecure (try using sslmode=require)`; startup logs warn but service still runs.
- **Cause:** Postgres down/absent (it is **optional**); wrong `RAG_DB_*` values; `RAG_DB_SSLMODE` mismatch (managed hosts need `require`, local compose needs `disable`).
- **Solution:** ForexAI is designed to run **without** the DB — fundamentals degrade to World Bank/ cached evidence. To use it: start a local `docker compose` Postgres or fix `RAG_DB_*` and `RAG_DB_SSLMODE`.
- **Verification:** `/ready` reports no missing required config; analysis 200 without DB-related warnings.

## 17. Docker issues

- **Symptoms:** container runs but MT5 scripts fail; `MetaTrader5` import errors inside Docker; build failures.
- **Cause:** **the Docker image is Linux and can never talk to MT5** — by design (`MetaTrader5==…; sys_platform == 'win32'` is skipped). Model artifacts are fetched at build time.
- **Solution:** run only the analysis service in Docker (with Twelve Data); run MT5 components (check scripts, bridge) natively on Windows. If build fails on artifacts, check network access to the GitHub release URL in the Dockerfile.
- **Verification:** `docker run -p 8000:8000 --env-file .env forexai-ai` → `/health` 200 **on the host**, while the bridge runs in PowerShell outside Docker.

## 18. Application crashes / restarts

- **Symptoms:** uvicorn or bridge process dies; connection drops mid-session.
- **Cause:** unhandled exception (uvicorn log will show the traceback); MT5 terminal restart (IPC dies); machine sleep.
- **Solution:** read the traceback — report genuine bugs with the log excerpt. The **sync worker is self-healing** (reconnects on next poll by design); the bridge and executor reconnect lazily on the next order. Restart order on any doubt: MT5 terminal → bridge → uvicorn.
- **Verification:** `/health` 200, bridge `/health` → `{"ok": true}`, connection check passes again.

### Extra: bridge-specific quick checks

| Symptom | Likely cause | Fix |
|---|---|---|
| Webhook never arrives | `WEBHOOK_ALLOWLIST` denies non-localhost; wrong URL | use `http://127.0.0.1:8799/signal?token=…` (localhost always allowed) |
| `401 missing or invalid token` | `BRIDGE_TOKEN` set but token missing/wrong in URL | match `?token=` to the env var |
| `404 not found` | POST to wrong path | path must be `/signal` |
| Bridge refuses `--live` | `MT5_DRY_RUN` not explicitly `false` | dual-key safety: set it in `.env` **and** pass `--live` |
| Response `400 not executable` | signal was HOLD/NO_TRADE or risk rejected | expected — see journal section B |

---

**Still stuck?** Capture: exact command, full console output (redact credentials),
`GET /ready` response, `python scripts/check_mt5_connection.py` output, and MT5's
last_error code — then compare with [`MT5_READINESS_REPORT.md`](MT5_READINESS_REPORT.md)
for known limitations vs bugs.

