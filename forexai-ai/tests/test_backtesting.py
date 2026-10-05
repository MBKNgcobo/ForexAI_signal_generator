"""Backtest realism: holding horizon, costs, opaque-barrier handling.

The engine is an offline analysis tool (excluded from coverage), so these
tests use tiny hand-built frames rather than artifacts or network data.
"""

import pandas as pd

from app.backtesting.engine import BacktestEngine
from app.backtesting.metrics import calculate_metrics


def _frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
    return frame


def _quiet_rows(
    count: int,
    close: float = 1.1000,
    atr: float = 0.0010,
) -> list[dict]:
    return [
        {
            "datetime": f"2026-01-01T00:{i:02d}:00Z",
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "atr_14": atr,
            "buy_probability": 0.1,
            "sell_probability": 0.1,
        }
        for i in range(count)
    ]


def _signal_row(
    minute: int,
    *,
    direction: str = "BUY",
    close: float = 1.1000,
    atr: float = 0.0010,
) -> dict:
    buy = 0.9 if direction == "BUY" else 0.1
    sell = 0.9 if direction == "SELL" else 0.1
    return {
        "datetime": f"2026-01-01T00:{minute:02d}:00Z",
        "open": close,
        "high": close + 0.0002,
        "low": close - 0.0002,
        "close": close,
        "atr_14": atr,
        "buy_probability": buy,
        "sell_probability": sell,
    }


def test_time_exit_when_no_barrier_inside_holding_window():
    rows = [_signal_row(0)]
    # Flat candles: neither the take-profit nor the stop-loss is touched.
    rows.extend(_quiet_rows(5))
    frame = _frame(rows)

    engine = BacktestEngine(
        stop_loss_atr=1.0,
        take_profit_atr=1.5,
        max_holding_period=2,
    )

    trades = engine.run(frame, probability_threshold=0.6)

    assert len(trades) == 1

    trade = trades[0]

    assert trade.result == "TIME_EXIT"
    assert trade.exit_price == frame.iloc[2]["close"]
    assert trade.profit == 0.0
    assert trade.cost == 0.0


def test_holding_window_is_respected_not_extended_to_end_of_file():
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(9))
    # A take-profit hit far beyond the holding window must not be reached.
    rows.append(
        {
            "datetime": "2026-01-01T00:10:00Z",
            "open": 1.1000,
            "high": 1.2000,
            "low": 1.0990,
            "close": 1.1500,
            "atr_14": 0.0010,
            "buy_probability": 0.1,
            "sell_probability": 0.1,
        }
    )
    frame = _frame(rows)

    engine = BacktestEngine(max_holding_period=2)

    trades = engine.run(frame, probability_threshold=0.6)

    assert len(trades) == 1
    assert trades[0].result == "TIME_EXIT"


def test_costs_reduce_profit_and_are_recorded():
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(3))
    frame = _frame(rows)

    engine = BacktestEngine(
        max_holding_period=2,
        spread=0.0002,
        commission=0.0001,
        slippage=0.0001,
    )

    trades = engine.run(frame, probability_threshold=0.6)

    assert len(trades) == 1

    trade = trades[0]

    # spread (0.0002) + 2x slippage (0.0002) + commission (0.0001).
    assert trade.cost == 0.0005
    assert trade.profit == -0.0005


def test_ambiguous_candle_records_zero_profit_and_no_cost():
    # One candle touches both barriers; the conservative outcome applies.
    rows = [
        _signal_row(0),
        {
            "datetime": "2026-01-01T00:01:00Z",
            "open": 1.1000,
            "high": 1.2000,
            "low": 1.0000,
            "close": 1.1000,
            "atr_14": 0.0010,
            "buy_probability": 0.1,
            "sell_probability": 0.1,
        },
    ]
    frame = _frame(rows)

    engine = BacktestEngine(spread=0.0002)

    trades = engine.run(frame, probability_threshold=0.6)

    assert len(trades) == 1
    assert trades[0].result == "AMBIGUOUS"
    assert trades[0].profit == 0.0
    assert trades[0].cost == 0.0


def test_metrics_include_time_exits_expectancy_and_averages():
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(3))
    frame = _frame(rows)

    engine = BacktestEngine(max_holding_period=2)
    trades = engine.run(frame, probability_threshold=0.6)

    metrics = calculate_metrics(trades)

    assert metrics["total_trades"] == 1
    assert metrics["time_exits"] == 1
    assert metrics["total_profit"] == 0.0
    assert metrics["expectancy"] == 0.0
    # No WIN/LOSS barrier trades in this fixture.
    assert metrics["avg_win"] == 0.0
    assert metrics["avg_loss"] == 0.0


def test_gross_and_net_are_reported_separately():
    # SQA C-02: a costed backtest must expose gross edge and net P/L
    # independently so costs cannot hide inside a single profit number.
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(3))
    frame = _frame(rows)

    engine = BacktestEngine(
        max_holding_period=2,
        spread=0.0002,
        commission=0.0001,
        slippage=0.0001,
    )
    trades = engine.run(frame, probability_threshold=0.6)

    metrics = calculate_metrics(trades)

    assert metrics["total_cost"] == 0.0005
    assert metrics["gross_profit"] == 0.0
    assert metrics["net_profit"] == -0.0005
    assert metrics["total_profit"] == metrics["net_profit"]
    # gross - cost reconstructs net: no hidden drag.
    assert metrics["gross_profit"] - metrics["total_cost"] == metrics["net_profit"]


def test_frictionless_backtest_reports_zero_cost_explicitly():
    # Zero-cost runs stay valid (baseline comparisons) but must say so via
    # total_cost == 0 rather than omitting the field.
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(3))
    frame = _frame(rows)

    engine = BacktestEngine(max_holding_period=2)
    trades = engine.run(frame, probability_threshold=0.6)

    metrics = calculate_metrics(trades)

    assert metrics["total_cost"] == 0.0
    assert metrics["gross_profit"] == metrics["net_profit"]
