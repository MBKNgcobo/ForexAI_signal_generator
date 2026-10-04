"""Signal bridge: payload gating, mapping, drift guard, HTTP mapping."""

import sys
import types

import pytest

from app.broker import mt5_executor as exec_mod
from app.broker.mt5_executor import MT5ExecutionError, MT5TradeExecutor
from app.broker.signal_bridge import (
    SignalBridge,
    SignalRejectedError,
    handle_signal_payload,
    prepare_order_request,
    signal_token_valid,
)


def _payload(
    direction="BUY",
    approved=True,
    entry=1.10010,
    sl=1.09510,
    tp=1.10760,
    conf=0.80,
    symbol="EURUSD",
    timeframe="FifteenMinutes",
    **extra,
):
    data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "final_decision": {
            "direction": direction,
            "confidence": conf,
            "reasoning": "test signal",
        },
        "risk_assessment": {
            "risk_level": "low",
            "approved": approved,
            "agreement": 0.80,
            "reason": "test",
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": 1.5,
        },
    }
    data.update(extra)
    return data


@pytest.fixture
def fake_mt5(monkeypatch):
    sent: list = []

    def _order_send(payload):
        sent.append(payload)
        return types.SimpleNamespace(
            retcode=10009,
            order=777,
            price=payload["price"],
            volume=payload["volume"],
            comment="done",
        )

    fake = types.SimpleNamespace(
        TRADE_ACTION_DEAL=1,
        TRADE_ACTION_PENDING=5,
        ORDER_TYPE_BUY=0,
        ORDER_TYPE_SELL=1,
        ORDER_TYPE_BUY_LIMIT=2,
        ORDER_TYPE_SELL_LIMIT=3,
        ORDER_TYPE_BUY_STOP=4,
        ORDER_TYPE_SELL_STOP=5,
        ORDER_FILLING_FOK=0,
        ORDER_FILLING_IOC=1,
        ORDER_FILLING_RETURN=2,
        ORDER_TIME_GTC=0,
        symbol_info=lambda s: types.SimpleNamespace(
            name=s,
            digits=5,
            point=0.00001,
            filling_mode=1,
            volume_min=0.01,
            volume_max=100.0,
        ),
        symbols_get=lambda p: [],
        symbol_select=lambda s, f: True,
        symbol_info_tick=lambda s: types.SimpleNamespace(
            time=1_700_000_600, bid=1.10000, ask=1.10020, last=1.1001
        ),
        order_send=_order_send,
        last_error=lambda: (10013, "invalid request"),
    )
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(exec_mod, "connect", lambda **kw: None)
    monkeypatch.setattr(exec_mod, "shutdown", lambda **kw: None)
    monkeypatch.delenv("MT5_DRY_RUN", raising=False)
    return fake, sent


def _bridge(**kw) -> SignalBridge:
    return SignalBridge(executor=MT5TradeExecutor(), **kw)


# -- pure mapping (no terminal) --------------------------------------------


def test_buy_payload_maps_to_market_buy():
    req = prepare_order_request(_payload(), volume=0.02)

    assert req.symbol == "EURUSD"
    assert req.side.value == "buy"
    assert req.order_kind.value == "market"
    assert req.volume == 0.02
    assert req.sl == 1.09510
    assert req.tp == 1.10760
    assert req.comment.startswith("sig BUY FifteenMinutes")
    assert len(req.comment) <= 31


def test_sell_payload_maps_to_sell():
    req = prepare_order_request(
        _payload(
            direction="SELL",
            entry=1.10010,
            sl=1.10510,
            tp=1.09510,
        ),
        volume=0.01,
    )

    assert req.side.value == "sell"
    assert "sig SELL" in req.comment


@pytest.mark.parametrize("direction", ["HOLD", "NO_TRADE", "", "BUY?"])
def test_non_executable_directions_rejected(direction):
    with pytest.raises(SignalRejectedError):
        prepare_order_request(_payload(direction=direction), volume=0.01)


def test_missing_final_decision_rejected():
    data = _payload()
    del data["final_decision"]

    with pytest.raises(SignalRejectedError, match="direction"):
        prepare_order_request(data, volume=0.01)


def test_risk_not_approved_rejected():
    with pytest.raises(SignalRejectedError, match="approved"):
        prepare_order_request(
            _payload(approved=False), volume=0.01
        )


def test_missing_stop_loss_rejected():
    with pytest.raises(SignalRejectedError, match="exit plan"):
        prepare_order_request(_payload(sl=None), volume=0.01)


def test_missing_take_profit_rejected():
    with pytest.raises(SignalRejectedError, match="exit plan"):
        prepare_order_request(_payload(tp=None), volume=0.01)


def test_missing_entry_rejected():
    with pytest.raises(SignalRejectedError, match="entry_price"):
        prepare_order_request(_payload(entry=None), volume=0.01)


def test_missing_symbol_rejected():
    with pytest.raises(SignalRejectedError, match="symbol"):
        prepare_order_request(_payload(symbol=None), volume=0.01)


def test_min_confidence_gate():
    with pytest.raises(SignalRejectedError, match="confidence"):
        prepare_order_request(
            _payload(conf=0.60), volume=0.01, min_confidence=0.75
        )

    # High enough: passes.
    req = prepare_order_request(
        _payload(conf=0.80), volume=0.01, min_confidence=0.75
    )
    assert req.volume == 0.01


def test_sl_equal_tp_becomes_signal_error():
    with pytest.raises(SignalRejectedError, match="failed validation"):
        prepare_order_request(_payload(sl=1.10000, tp=1.10000), 0.01)


def test_non_dict_payload_rejected():
    with pytest.raises(SignalRejectedError, match="JSON object"):
        prepare_order_request(["not", "a", "dict"], volume=0.01)


# -- execute pipeline (fake terminal) --------------------------------------


def test_execute_dry_run_sends_nothing(fake_mt5):
    _, sent = fake_mt5

    result = _bridge().execute(_payload())  # env default = dry-run

    assert result.dry_run is True
    assert result.ticket is None
    assert sent == []


def test_execute_live_returns_ticket(fake_mt5):
    _, sent = fake_mt5
    bridge = _bridge()
    bridge.executor.dry_run = False

    result = bridge.execute(_payload())

    assert result.dry_run is False
    assert result.ticket == 777
    assert len(sent) == 1
    # The order payload carries the signal's exits verbatim.
    assert sent[0]["sl"] == 1.09510
    assert sent[0]["tp"] == 1.10760


def test_drift_guard_allows_small_drift(fake_mt5):
    # entry 1.10010 vs ask 1.10020 = 10 points < 100 max.
    result = _bridge().execute(_payload())

    assert result.dry_run is True


def test_drift_guard_rejects_stale_entry(fake_mt5):
    # entry 1.11000 vs ask 1.10020 = 980 points > 100 max.
    with pytest.raises(SignalRejectedError, match="entry drift"):
        _bridge().execute(_payload(entry=1.11000))


def test_drift_guard_can_be_disabled(fake_mt5):
    bridge = _bridge(max_entry_drift_points=0.0)

    result = bridge.execute(_payload(entry=1.11000))

    assert result.dry_run is True  # stale entry accepted when disabled


# -- HTTP-shaped handler ---------------------------------------------------


def test_handler_accepts_valid_signal(fake_mt5):
    status, body = handle_signal_payload(_bridge(), _payload())

    assert status == 200
    assert body["accepted"] is True
    assert body["dry_run"] is True
    assert body["order_payload"]["type"] == 0  # BUY


def test_handler_rejects_hold_with_400(fake_mt5):
    status, body = handle_signal_payload(_bridge(), _payload("HOLD"))

    assert status == 400
    assert body["accepted"] is False
    assert "not executable" in body["error"]


def test_handler_rejects_non_dict_with_400(fake_mt5):
    status, body = handle_signal_payload(_bridge(), "garbage")

    assert status == 400


def test_handler_maps_terminal_failure_to_503(fake_mt5):
    fake, _ = fake_mt5
    fake.order_send = lambda p: None  # terminal hiccup
    bridge = _bridge()
    bridge.executor.dry_run = False

    status, body = handle_signal_payload(bridge, _payload())

    assert status == 503
    assert body["accepted"] is False


def test_handler_maps_execution_error_to_503(fake_mt5):
    class _BoomBridge(SignalBridge):
        def execute(self, payload, dry_run=None):
            raise MT5ExecutionError("terminal gone")

    status, body = handle_signal_payload(_BoomBridge(MT5TradeExecutor()), {})

    assert status == 503
    assert "terminal gone" in body["error"]


# -- URL token auth ---------------------------------------------------------


def test_token_valid_when_matching():
    assert signal_token_valid("/signal?token=s3cret", "s3cret") is True


def test_token_rejected_when_missing():
    assert signal_token_valid("/signal", "s3cret") is False


def test_token_rejected_when_wrong():
    assert (
        signal_token_valid("/signal?token=wrong", "s3cret") is False
    )


def test_token_auth_off_when_unconfigured():
    # No expected token -> localhost-only mode, everything allowed.
    assert signal_token_valid("/signal?token=anything", None) is True
    assert signal_token_valid("/signal", "") is True


def test_unicode_token_never_raises():
    assert (
        signal_token_valid("/signal?token=%F0%9F%94%A5", "s3cret")
        is False
    )
