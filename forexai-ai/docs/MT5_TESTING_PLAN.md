# ForexAI — MT5 Paper / Demo Testing Strategy

> **Purpose:** let *you* determine, with evidence, whether ForexAI's signals are
> good enough to justify anything beyond paper testing.
> **This plan does not encourage live trading.** Reaching the final stage is a
> decision to *evaluate whether* live testing is appropriate — never an
> instruction to do it.
>
> **Golden rule:** a working program is not a profitable strategy. An AI-generated
> BUY/SELL signal is a *hypothesis*, not proof. Only statistically meaningful,
> cost-adjusted, forward-tested results count.

---

## Stage 0 — Preconditions (before any trading test)

- [ ] All 8 tests in [`MT5_USER_GUIDE.md`](MT5_USER_GUIDE.md) §5 pass.
- [ ] `MT5_DRY_RUN=true` confirmed in `.env`.
- [ ] Quant model artifacts present (`models/*.joblib`, or run
      `python scripts/fetch_model_artifacts.py`).
- [ ] Test suite green: `python -m pytest -q` (366+ tests).
- [ ] Journal ready: copy [`MT5_TRADE_JOURNAL.md`](MT5_TRADE_JOURNAL.md).

---

## Stage 1 — Backtesting (no market risk)

**Goal:** see how the strategy behaved on *historical* data before any live signal.

1. The project ships a backtesting engine: `app/backtesting/engine.py`
   (`spread`, `commission`, `slippage` parameters — use realistic values:
   the codebase validates with `spread=0.00015`, `slippage=0.00005` for EURUSD).
2. Run the included threshold analysis to understand trade frequency vs net:
   `app/backtesting/threshold_analysis.py` and `python app/backtesting/run_backtest.py`.
3. Read `app/backtesting/metrics.py` outputs: net, profit factor, trade count.

**Pass criteria to proceed:** results are not catastrophic *after* costs, and you
understand the strategy's assumptions (1.0×ATR stop, 1.5×target, 15m focus).

**Honesty check:** the documented validation covers **EURUSD 15m, ~113 days**
(PF 1.31 at threshold 0.50, net of costs). One pair × one timeframe × ~4 months
is a *small sample*. Do not extrapolate.

## Stage 2 — Historical / signal replay (no market risk)

**Goal:** compare the *full AI pipeline* (not just the quant model) against
historical candles.

1. Pick several past periods — including a trend, a range, and a high-impact
   news week.
2. Because data comes through `MarketDataCache` with a 30 s TTL, replay is
   manual: note the candle timestamps you would have traded, generate signals at
   the time, and journal them — or accept that true historical replay of the LLM
   agents is **not implemented** (a documented gap; the quant component *is*
   replayable via backtests).
3. Track for each signal: direction, confidence, whether entry/SL/TP levels were
   geometrically valid, and what actually happened next (inspect in MT5 strategy
   tester or on charts).

**Pass criteria:** signal logic behaves sanely (no inverted SL/TP, no confident
BUY into obvious collapse, sensible NO_TRADE rate).

## Stage 3 — Paper / simulated trading (MT5 DRY-RUN mode)

**Goal:** exercise the entire software pipeline with **zero** broker contact.

1. Keep `MT5_DRY_RUN=true`.
2. Run the service + bridge; feed it signals via webhook for several days.
3. For every signal the bridge accepts (`"dry_run": true`), record a **simulated**
   entry in the journal using MT5's displayed bid/ask at that moment.
4. Manually resolve each simulated trade when SL/TP would have hit (check the
   chart) and compute simulated P/L including spread.

**Minimum duration: 2 weeks, ≥ 20 simulated trades.**
**Pass criteria:** the pipeline is reliable (no crashes, no malformed payloads,
rejections happen for the *right* reasons), and simulated results are not
obviously negative after spread.

## Stage 4 — MT5 DEMO account (first real orders)

**Goal:** measure *execution reality* — slippage, spread, broker behaviour.

1. Dual-key a **single** deliberate order first (`MT5_DRY_RUN=false` +
   `--live`), verify ticket, SL/TP placement, then return to dry-run until you
   are confident in the flow.
2. Trade the **smallest size** (`MT5_SIGNAL_VOLUME=0.01`) on **one pair
   (EURUSD)**, **one timeframe (15m)**.
3. Only take signals where `risk_assessment.approved == true` and confidence
   meets your personal bar (e.g. ≥ 0.6).
4. Journal **every** trade: entry time vs signal time (latency), spread at
   entry, requested vs filled price (slippage), outcome.

**Minimum: 2 weeks, ≥ 15 demo trades.**
**Pass criteria:** fills match expectations within tolerance, no rejected/malformed
orders, manual journal reconciles with MT5 Account History exactly.

## Stage 5 — Extended demo testing (statistical sample)

**Goal:** accumulate enough trades for the metrics below to mean something —
with the system running as it would "for real".

1. Before starting, implement (or consciously accept as a manual-control
   limitation) the P0 safety items in [`MT5_READINESS_REPORT.md`](MT5_READINESS_REPORT.md):
   duplicate-signal protection, a kill procedure, and open-position caps.
   For a supervised, attended session you can rely on **you** as the kill switch.
2. Expand to 2–3 pairs max, still the same timeframe first; add a second
   timeframe only after 30+ trades.
3. Run only during attended sessions. Never overnight without explicit SL on
   every position (the bridge always sends SL/TP — verify in MT5).
4. Record everything automatically available (MT5 history export) plus the
   journal's qualitative fields.

**Minimum duration: 4–8 weeks OR ≥ 50 trades, whichever is later.**

## Stage 6 — Evaluate whether live testing is appropriate

**Do not proceed unless ALL of the following hold:**

- [ ] ≥ 50 demo trades across ≥ 6 weeks and ≥ 2 market regimes
      (trending + ranging, plus at least one news-heavy period).
- [ ] Win rate, profit factor and drawdown (below) meet *your* predefined
      thresholds — defined *before* you look at the results.
- [ ] Results survive cost adjustment (spread + slippage actually observed).
- [ ] No unexplained execution failures in the entire period.
- [ ] P0 safety features (kill switch, caps, dedup) are implemented or you have
      a written manual procedure.
- [ ] You are psychologically willing to lose the entire live allocation.

If any box is unchecked → stay on demo. **Re-run Stage 5 for another cycle.**

> Even then, any live phase starts at 0.01 lots with a hard money cap you can
> afford to lose completely. This repository does not provide, endorse, or
> automate live trading.

---

## Metrics to track (every stage ≥ 3)

Record these from the journal + MT5 Account History:

| Metric | How to compute | Why it matters |
|---|---|---|
| Number of trades | count journal rows | sample size — under 30, ignore everything else |
| Winning / losing trades | count by result | base rates |
| Win rate | wins ÷ trades | must be read together with R:R |
| Average win / average loss | mean P/L per outcome | payoff size |
| **Profit factor** | gross profit ÷ gross loss | > 1.0 = profitable; > 1.3 = interesting |
| **Maximum drawdown** | largest equity peak-to-trough | survival check |
| Sharpe ratio (optional) | mean excess return ÷ std dev of returns | only meaningful ≥ 30 trades, low value for few samples |
| Risk/reward realized | avg win ÷ avg loss | compare to the intended 1.5 |
| Average holding time | exit time − entry time | matches your timeframe? |
| Spread at entry/exit | MT5 tick / journal | cost drag |
| Slippage | fill price vs requested | execution quality |
| Signal accuracy | % signals that hit TP before SL | the core question |
| False signals | confident signals that failed immediately | calibration quality |
| Long vs short performance | split by direction | one side often broken |
| Performance by pair | group by symbol | overfitting to EURUSD? |
| Performance by timeframe | group by timeframe | — |
| Performance by market condition | label trend/range/news week | robustness |
| Signal-to-fill latency | fill time − signal time | bridge/webhook delays |

**Weekly review ritual (15 min):** update the table, note anomalies in the
journal's Notes column, decide continue/pause.

## Minimum recommended testing periods

| Stage | Minimum duration | Minimum trades | Can you skip it? |
|---|---|---|---|
| 1 Backtest | — | full historical run | No |
| 2 Signal replay | 1 week of manual review | ≥ 20 signals | Only if Stage 1 was strong |
| 3 Dry-run paper | 2 weeks | ≥ 20 simulated | No |
| 4 MT5 demo (small) | 2 weeks | ≥ 15 real demo fills | No |
| 5 Extended demo | 4–8 weeks | ≥ 50 | No |
| 6 Live evaluation | — | — | **Never automatic** |

Total realistic calendar time from zero to a *decision*: **~2–3 months**.
Anything shorter is a smoke test, not an evaluation.

