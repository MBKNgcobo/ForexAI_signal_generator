"""Risk-based position sizing tests (SQA C-05).

The sizing math is the money-critical path, so it gets direct coverage:
formula correctness, per-instrument pip value (5-digit vs JPY), clamping to the
broker's volume limits, step snapping (never rounding a risk up), and the
opt-in behaviour (RISK_PERCENT=0 keeps the fixed-lot default unchanged).
"""

import pytest

from app.broker.position_sizing import (
    compute_bridge_volume,
    compute_position_volume,
    pip_size,
)


def test_pip_size_five_digit_vs_jpy():
    assert pip_size("EURUSD") == pytest.approx(0.0001)
    assert pip_size("USDJPY") == pytest.approx(0.01)


def test_sizes_to_risk_one_percent():
    # Equity 10,000, risk 1% -> 100 risked. Stop 20 pips (0.0020) on EURUSD:
    # loss per lot = 20 pips * 10 = 200 -> volume = 100 / 200 = 0.5 lots.
    volume = compute_position_volume(
        equity=10_000.0,
        risk_percent=1.0,
        entry_price=1.1000,
        stop_loss=1.0980,
        symbol="EURUSD",
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
    assert volume == pytest.approx(0.5)


def test_high_atr_pair_sizes_smaller_than_low_atr():
    # Same equity/risk, wider stop -> smaller lot, so capital at risk is equal.
    wide = compute_position_volume(
        equity=10_000.0,
        risk_percent=1.0,
        entry_price=1.1000,
        stop_loss=1.0900,  # 100 pips
        symbol="EURUSD",
    )
    narrow = compute_position_volume(
        equity=10_000.0,
        risk_percent=1.0,
        entry_price=1.1000,
        stop_loss=1.0980,  # 20 pips
        symbol="EURUSD",
    )
    assert wide < narrow
    assert wide == pytest.approx(0.1)
    assert narrow == pytest.approx(0.5)


def test_jpy_pair_uses_larger_pip_value():
    # USDJPY 3-digit: pip = 0.01. Entry 150.00, stop 149.50 -> 50 pips.
    # loss per lot = 50 * 10 = 500; risk 100 -> 0.2 lots.
    volume = compute_position_volume(
        equity=10_000.0,
        risk_percent=1.0,
        entry_price=150.00,
        stop_loss=149.50,
        symbol="USDJPY",
    )
    assert volume == pytest.approx(0.2)


def test_clamps_to_volume_max():
    # Tiny stop (1 pip) with a large risk budget -> raw volume far above the
    # broker maximum -> clamped to volume_max.
    volume = compute_position_volume(
        equity=1_000_000.0,
        risk_percent=10.0,
        entry_price=1.10000,
        stop_loss=1.09990,  # 1 pip
        symbol="EURUSD",
        volume_max=5.0,
    )
    assert volume == pytest.approx(5.0)


def test_clamps_to_volume_min_when_risk_too_small():
    # Enormous stop relative to equity -> raw volume below the broker minimum.
    volume = compute_position_volume(
        equity=100.0,
        risk_percent=0.5,
        entry_price=1.1000,
        stop_loss=1.0000,  # 1000 pips
        symbol="EURUSD",
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
    assert volume == pytest.approx(0.01)


def test_snaps_down_to_volume_step_never_rounds_risk_up():
    # Raw volume 0.505 with step 0.01 must floor to 0.50, not round to 0.51.
    volume = compute_position_volume(
        equity=10_100.0,   # 1% = 101 risked
        risk_percent=1.0,
        entry_price=1.1000,
        stop_loss=1.0980,  # 20 pips -> loss/lot 200 -> raw 0.505
        symbol="EURUSD",
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
    assert volume == pytest.approx(0.50)


def test_zero_equity_or_risk_falls_back_to_min():
    assert compute_position_volume(
        equity=0.0, risk_percent=1.0, entry_price=1.1,
        stop_loss=1.09, symbol="EURUSD",
    ) == pytest.approx(0.01)
    assert compute_position_volume(
        equity=10_000.0, risk_percent=0.0, entry_price=1.1,
        stop_loss=1.09, symbol="EURUSD",
    ) == pytest.approx(0.01)


def test_zero_stop_distance_falls_back_to_min():
    assert compute_position_volume(
        equity=10_000.0, risk_percent=1.0, entry_price=1.1,
        stop_loss=1.1, symbol="EURUSD",
    ) == pytest.approx(0.01)


# -- bridge wiring (opt-in behaviour) ----------------------------------------


def _payload(entry=1.1000, sl=1.0980, symbol="EURUSD"):
    return {
        "symbol": symbol,
        "risk_assessment": {
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": 1.1150,
        },
    }


def test_bridge_sizer_is_noop_when_risk_percent_zero(monkeypatch):
    from app.config import risk_percent

    monkeypatch.delenv("RISK_PERCENT", raising=False)
    risk_percent.cache_clear()

    volume = compute_bridge_volume(
        _payload(), equity=10_000.0, fallback_volume=0.01
    )
    # Default RISK_PERCENT=0 -> fixed lot preserved exactly.
    assert volume == pytest.approx(0.01)


def test_bridge_sizer_sizes_when_risk_percent_set(monkeypatch):
    from app.config import risk_percent

    monkeypatch.setenv("RISK_PERCENT", "1.0")
    risk_percent.cache_clear()

    volume = compute_bridge_volume(
        _payload(), equity=10_000.0, fallback_volume=0.01
    )
    # 1% of 10k = 100 risked; 20-pip stop -> 0.5 lots.
    assert volume == pytest.approx(0.5)


def test_bridge_sizer_falls_back_when_levels_missing(monkeypatch):
    from app.config import risk_percent

    monkeypatch.setenv("RISK_PERCENT", "1.0")
    risk_percent.cache_clear()

    volume = compute_bridge_volume(
        {"symbol": "EURUSD", "risk_assessment": {}},
        equity=10_000.0,
        fallback_volume=0.03,
    )
    assert volume == pytest.approx(0.03)
