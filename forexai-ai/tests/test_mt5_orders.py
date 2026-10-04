"""MT5 trade executor (Phase 3): payload mapping, risk rules, dry-run."""

import sys
import types

import pytest

from app.broker import mt5_executor as exec_mod
from app.broker.mt5_executor import (
    MT5ExecutionError,
    MT5TradeExecutor,
    OrderKind,
    OrderRequest,
    OrderSide,
)


def _make_fake(**overrides):
    sent: list = []

    def _order_send(payload):
        sent.append(payload)
        return types.SimpleNamespace(
            retcode=10009,
            order=4242,
            price=payload["price"],
            volume=payload["volume"],
            comment="done",
        )

    defaults = {
        "TRADE_ACTION_DEAL": 1,
        "TRADE_ACTION_PENDING": 5,
        "ORDER_TYPE_BUY": 0,
        "ORDER_TYPE_SELL": 1,
        "ORDER_TYPE_BUY_LIMIT": 2,
        "ORDER_TYPE_SELL_LIMIT": 3,
        "ORDER_TYPE_BUY_STOP": 4,
        "ORDER_TYPE_SELL_STOP": 5,
        "ORDER_FILLING_FOK": 0,
        "ORDER_FILLING_IOC": 1,
        "ORDER_FILLING_RETURN": 2,
        "ORDER_TIME_GTC": 0,
        "symbol_info": lambda s: types.SimpleNamespace(
            name=s,
            digits=5,
            filling_mode=1,  # FOK allowed
            volume_min=0.01,
            volume_max=100.0,
        ),
        "symbols_get": lambda p: [],
        "symbol_select": lambda s, f: True,
        "symbol_info_tick": lambda s: types.SimpleNamespace(
            time=1_700_000_600, bid=1.10000, ask=1.10020, last=1.1001
        ),
        "order_send": _order_send,
        "last_error": lambda: (10013, "invalid request"),
    }
    defaults.update(overrides)

    return types.SimpleNamespace(**defaults), sent


@pytest.fixture
def fake_mt5(monkeypatch):
    fake, sent = _make_fake()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(exec_mod, "connect", lambda **kw: None)
    monkeypatch.setattr(exec_mod, "shutdown", lambda: None)
    # No MT5_DRY_RUN in env -> config default is dry-run = True.
    monkeypatch.delenv("MT5_DRY_RUN", raising=False)
    return fake, sent


def _market_buy(**kw) -> OrderRequest:
    defaults = dict(
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_kind=OrderKind.MARKET,
        volume=0.01,
        sl=1.0992,
        tp=1.1022,
    )
    defaults.update(kw)
    return OrderRequest(**defaults)


# -- payload building ------------------------------------------------------


def test_market_buy_payload_uses_ask(fake_mt5):
    fake, sent = fake_mt5
    ex = MT5TradeExecutor()

    result = ex.send(_market_buy())  # dry-run by default

    assert result.dry_run is True
    assert sent == []  # nothing reached order_send
    p = result.payload
    assert p["action"] == 1  # TRADE_ACTION_DEAL
    assert p["type"] == 0  # ORDER_TYPE_BUY
    assert p["price"] == 1.10020  # ask, rounded to digits
    assert p["sl"] == 1.0992 and p["tp"] == 1.1022
    assert p["symbol"] == "EURUSD"
    assert p["type_filling"] == 0  # FOK (filling_mode bit0)


def test_market_sell_payload_uses_bid(fake_mt5):
    ex = MT5TradeExecutor()

    result = ex.send(
        _market_buy(side=OrderSide.SELL, sl=1.1010, tp=1.0990),
        dry_run=True,
    )

    p = result.payload
    assert p["type"] == 1  # ORDER_TYPE_SELL
    assert p["price"] == 1.10000  # bid


def test_limit_sell_payload_is_pending(fake_mt5):
    ex = MT5TradeExecutor()

    result = ex.send(
        _market_buy(
            side=OrderSide.SELL,
            order_kind=OrderKind.LIMIT,
            price=1.10150,
            sl=1.10250,
            tp=1.09950,
        ),
        dry_run=True,
    )

    p = result.payload
    assert p["action"] == 5  # TRADE_ACTION_PENDING
    assert p["type"] == 3  # ORDER_TYPE_SELL_LIMIT
    assert p["price"] == 1.1015


def test_stop_buy_payload_is_pending(fake_mt5):
    ex = MT5TradeExecutor()

    result = ex.send(
        _market_buy(
            order_kind=OrderKind.STOP,
            price=1.10150,
            sl=1.10050,
            tp=1.10350,
        ),
        dry_run=True,
    )

    p = result.payload
    assert p["action"] == 5
    assert p["type"] == 4  # ORDER_TYPE_BUY_STOP


def test_string_enums_are_coerced(fake_mt5):
    req = _market_buy(side="buy", order_kind="market")

    assert req.side is OrderSide.BUY
    assert req.order_kind is OrderKind.MARKET


# -- rigid risk validation -------------------------------------------------


def test_missing_sl_is_rejected():
    with pytest.raises(ValueError, match="mandatory"):
        _market_buy(sl=0.0)


def test_missing_tp_is_rejected():
    with pytest.raises(ValueError, match="mandatory"):
        _market_buy(tp=0.0)


def test_sl_equal_tp_is_rejected():
    with pytest.raises(ValueError, match="must differ"):
        _market_buy(sl=1.1000, tp=1.1000)


def test_limit_without_price_is_rejected():
    with pytest.raises(ValueError, match="require a price"):
        _market_buy(order_kind=OrderKind.LIMIT, price=None)


def test_buy_sl_above_fill_price_is_rejected(fake_mt5):
    # sl=1.1005 sits ABOVE the ask (1.10020) — nonsensical for a buy.
    ex = MT5TradeExecutor()

    with pytest.raises(ValueError, match="Risk bounds"):
        ex.send(_market_buy(sl=1.1005, tp=1.1022), dry_run=True)


def test_sell_tp_above_fill_price_is_rejected(fake_mt5):
    ex = MT5TradeExecutor()

    with pytest.raises(ValueError, match="Risk bounds"):
        ex.send(
            _market_buy(
                side=OrderSide.SELL, sl=1.1010, tp=1.1001  # tp not below
            ),
            dry_run=True,
        )


def test_volume_below_symbol_minimum_is_rejected(fake_mt5):
    ex = MT5TradeExecutor()

    with pytest.raises(ValueError, match="below symbol minimum"):
        ex.send(_market_buy(volume=0.001), dry_run=True)


# -- live path (explicitly opted in) ---------------------------------------


def test_live_send_returns_ticket(fake_mt5):
    fake, sent = fake_mt5
    ex = MT5TradeExecutor(dry_run=False)

    result = ex.send(_market_buy())

    assert result.dry_run is False
    assert result.retcode == 10009
    assert result.ticket == 4242
    assert len(sent) == 1  # exactly one order_send call


def test_partial_fill_retcode_10010_is_success(fake_mt5):
    fake, _ = fake_mt5
    fake.order_send = lambda p: types.SimpleNamespace(
        retcode=10010, order=7, price=p["price"], volume=0.005,
        comment="partial",
    )
    ex = MT5TradeExecutor(dry_run=False)

    result = ex.send(_market_buy())

    assert result.retcode == 10010
    assert result.ticket == 7


def test_rejected_retcode_raises_with_code(fake_mt5):
    fake, _ = fake_mt5
    fake.order_send = lambda p: types.SimpleNamespace(
        retcode=10016, order=0, comment="invalid stops"
    )
    ex = MT5TradeExecutor(dry_run=False)

    with pytest.raises(MT5ExecutionError, match="10016"):
        ex.send(_market_buy())


def test_order_send_none_raises_with_last_error(fake_mt5):
    fake, _ = fake_mt5
    fake.order_send = lambda p: None
    ex = MT5TradeExecutor(dry_run=False)

    with pytest.raises(MT5ExecutionError, match="returned None"):
        ex.send(_market_buy())


def test_order_send_exception_is_wrapped(fake_mt5):
    fake, _ = fake_mt5

    def _boom(payload):
        raise ConnectionError("IPC dropped")

    fake.order_send = _boom
    ex = MT5TradeExecutor(dry_run=False)

    with pytest.raises(MT5ExecutionError, match="IPC dropped"):
        ex.send(_market_buy())


# -- filling mode selection -------------------------------------------------


@pytest.mark.parametrize(
    "filling_mode,expected",
    [(1, 0), (2, 1), (0, 2)],  # FOK, IOC, RETURN
)
def test_filling_mode_from_symbol_bits(
    fake_mt5, filling_mode, expected
):
    fake, _ = fake_mt5
    base = fake.symbol_info("EURUSD")
    fake.symbol_info = lambda s: types.SimpleNamespace(
        name=s,
        digits=5,
        filling_mode=filling_mode,
        volume_min=0.01,
        volume_max=100.0,
    )
    assert base is not None

    result = MT5TradeExecutor().send(_market_buy(), dry_run=True)

    assert result.payload["type_filling"] == expected


# -- dry-run configuration --------------------------------------------------


def test_config_dry_run_defaults_true(monkeypatch):
    from app.config import mt5_dry_run

    monkeypatch.delenv("MT5_DRY_RUN", raising=False)
    assert mt5_dry_run() is True

    monkeypatch.setenv("MT5_DRY_RUN", "garbage")
    assert mt5_dry_run() is True  # typo can never enable live trading

    monkeypatch.setenv("MT5_DRY_RUN", "false")
    assert mt5_dry_run() is False


def test_explicit_arg_beats_env_false(fake_mt5, monkeypatch):
    _, sent = fake_mt5
    monkeypatch.setenv("MT5_DRY_RUN", "false")

    result = MT5TradeExecutor().send(_market_buy(), dry_run=True)

    assert result.dry_run is True
    assert sent == []


def test_env_false_makes_send_live_without_arg(fake_mt5, monkeypatch):
    _, sent = fake_mt5
    monkeypatch.setenv("MT5_DRY_RUN", "false")

    result = MT5TradeExecutor().send(_market_buy())

    assert result.dry_run is False
    assert len(sent) == 1

