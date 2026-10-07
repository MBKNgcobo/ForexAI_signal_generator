# ForexAI — MT5 Trade Journal

> Manual journal for the first testing phases. **No trade is complete until it
> is journaled.** Reconcile every row against MT5's **Account History** weekly.
>
> How to use: copy the blank table per week, fill one row per signal (even
> rejected/NO_TRADE signals — *those tell you about false-signal rate*), then
> update the summary sheet.

---

## A. Weekly trade log

One row per signal. Print or duplicate this table as needed.

| # | Date | Time (local + TZ) | Symbol | Timeframe | Signal (BUY/SELL/HOLD/NO_TRADE) | AI confidence | Technical analysis | Fundamental analysis | Quant direction / prob. | Risk approved? | Entry | Stop Loss | Take Profit | Position size (lots) | Risk % of account | Spread (pips) | Exit time | Exit price | P/L (cash) | P/L (pips) | Result (WIN/LOSS/BE/OPEN) | Reason for entry | Reason for exit | Market conditions | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | | | | | 0.01 | | | | | | | | | | |
| 2 | | | | | | | | | | | | | | 0.01 | | | | | | | | | | |
| 3 | | | | | | | | | | | | | | 0.01 | | | | | | | | | | |
| 4 | | | | | | | | | | | | | | 0.01 | | | | | | | | | | |
| 5 | | | | | | | | | | | | | | 0.01 | | | | | | | | | | |

**Field notes**

| Field | Where to get it |
|---|---|
| Signal | `final_decision.direction` from the `/analysis` response (or bridge log) |
| AI confidence | `final_decision.confidence` (0–1) |
| Technical analysis | `technical_analysis.summary` + direction/confidence |
| Fundamental analysis | `fundamental_analysis.summary` + direction/confidence |
| Quant direction / prob. | `quant_prediction.direction` + `risk_assessment.quant_probability` |
| Risk approved? | `risk_assessment.approved` — if `false`, entry columns stay empty |
| Entry / SL / TP | `risk_assessment.entry_price/stop_loss/take_profit`; confirm SL/TP on the MT5 ticket |
| Risk % of account | (entry−SL) × lots × pip value ÷ account balance |
| Spread | ask−bid at fill (MT5 tick or order details) |
| Exit price / time | MT5 Account History |
| Result | WIN (TP hit / closed green), LOSS (SL hit / closed red), BE, OPEN |
| Market conditions | e.g. `trend-up`, `range`, `news: NFP`, `low-liquidity`, `session: London` |
| Notes | latency, rejections, bridge errors, emotional notes, anything odd |

---

## B. Rejected / no-trade signals (false-signal surveillance)

| # | Date | Time | Symbol | Timeframe | Signal shown | Why not traded (400 reason / NO_TRADE / HOLD) | What price did afterwards |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |

> If the market moved strongly in the signal's direction after a rejection,
> note it — that measures what the gates cost you. If confident signals keep
> failing, that measures calibration.

---

## C. Weekly summary

| Week | Trades | Wins | Losses | BE | Win rate | Avg win | Avg loss | Profit factor | Max drawdown (week) | Cumulative P/L | Spread+slippage paid | Notes / anomalies |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | | | |
| 2 | | | | | | | | | | | | |
| 3 | | | | | | | | | | | | |
| 4 | | | | | | | | | | | | |

**Formulas**

- Win rate = wins ÷ (wins + losses)
- Profit factor = Σ profits ÷ Σ losses (absolute)
- Average win / average loss = mean of each group
- Max drawdown = largest peak-to-trough drop of cumulative equity in the period
- Risk : reward (realized) = avg win ÷ avg loss

---

## D. System / execution log (engineering events)

| Date | Event (startup, connect, dry-run order, live order, rejection, crash, restart) | Component (service / bridge / MT5) | Expected? | Actual behaviour | Follow-up |
|---|---|---|---|---|---|
| | | | | | |

---

## E. End-of-stage checklist (copy per stage of MT5_TESTING_PLAN.md)

- [ ] All signals from the period are in sections A **and** B
- [ ] Every A-row matches MT5 Account History (ticket, prices, P/L)
- [ ] Section C totals recomputed
- [ ] Execution events logged in D
- [ ] Go / no-go decision for the next stage recorded below

**Decision:** ______________________  **Date:** ______________________
