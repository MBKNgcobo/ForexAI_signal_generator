"""MT5 state synchronization (Phase 4): snapshots, diffs, worker."""

import sys
import time
import types

import pytest

from app.broker import mt5_sync as sync_mod
from app.broker.mt5_sync import (
    MT5StateSynchronizer,
    MT5SyncError,
)


def _position(ticket=100, sl=1.1000, **kw):
    defaults = dict(
        ticket=ticket,
        symbol="EURUSD",
        type=0,  # buy
        volume=0.01,
        price_open=1.10010,
        price_current=1.10020,
        sl=sl,
        tp=1.10500,
        profit=1.50,
        swap=0.0,
        magic=0,
        comment="test",
        time=1_700_000_000,
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def _order(ticket=500, type=2, **kw):
    defaults = dict(
        ticket=ticket,
        symbol="EURUSD",
        type=type,  # 2 = buy limit
        price_open=1.09500,
        volume_initial=0.10,
        volume_current=0.10,
        sl=1.09000,
        tp=1.10000,
        state=0,
        magic=0,
        comment="",
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def _account(balance=100_000.0, equity=100_010.0):
    return types.SimpleNamespace(
        login=113602898,
        balance=balance,
        equity=equity,
        margin=35.0,
        margin_free=99_975.0,
        currency="USD",
        trade_allowed=True,
    )


def _make_fake(positions=None, orders=None, account=None, **overrides):
    state = {
        "positions": positions or (),
        "orders": orders or (),
        "account": account if account is not None else _account(),
    }

    defaults = {
        "account_info": lambda: state["account"],
        "positions_get": lambda: state["positions"],
        "orders_get": lambda: state["orders"],
        "last_error": lambda: (10013, "invalid request"),
    }
    defaults.update(overrides)

    return types.SimpleNamespace(**defaults), state


@pytest.fixture
def fake_mt5(monkeypatch):
    fake, state = _make_fake(positions=(_position(),), orders=(_order(),))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(sync_mod, "connect", lambda **kw: None)
    monkeypatch.setattr(sync_mod, "shutdown", lambda: None)
    return fake, state


def _sync(**kw) -> MT5StateSynchronizer:
    return MT5StateSynchronizer(**kw)


# -- snapshot mapping ------------------------------------------------------


def test_snapshot_maps_all_domains(fake_mt5):
    sync = _sync()

    state = sync.snapshot()

    assert state.account.login == 113602898
    assert state.account.balance == 100_000.0

    pos = state.positions[0]
    assert pos.ticket == 100
    assert pos.side == "buy"
    assert pos.opened_at.tzinfo is not None  # UTC-normalized

    order = state.orders[0]
    assert order.ticket == 500
    assert order.kind == "buy_limit"


def test_positions_none_raises_with_retcode(fake_mt5):
    fake, state = fake_mt5
    state["positions"] = None

    with pytest.raises(MT5SyncError, match="positions_get.*10013"):
        _sync().snapshot()


def test_orders_none_raises(fake_mt5):
    fake, state = fake_mt5
    state["orders"] = None

    with pytest.raises(MT5SyncError, match="orders_get"):
        _sync().snapshot()


def test_account_none_raises(fake_mt5):
    fake, state = fake_mt5
    state["account"] = None

    with pytest.raises(MT5SyncError, match="account_info"):
        _sync().snapshot()


# -- diffing ---------------------------------------------------------------


def test_first_poll_is_initial_baseline(fake_mt5):
    report = _sync().poll_once()

    assert report.initial is True
    assert report.has_drift is False


def test_no_changes_means_no_drift(fake_mt5):
    sync = _sync()
    sync.poll_once()

    report = sync.poll_once()

    assert report.initial is False
    assert report.has_drift is False


def test_opened_and_closed_positions_detected(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()
    sync.poll_once()

    # Position 100 closes; 200 opens.
    state["positions"] = (_position(ticket=200, type=1, sl=1.1100),)

    report = sync.poll_once()

    assert report.closed_positions == (100,)
    assert report.opened_positions == (200,)
    assert report.has_drift is True


def test_modified_position_sl_change_detected(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()
    sync.poll_once()

    state["positions"] = (_position(ticket=100, sl=1.1010),)  # sl moved

    report = sync.poll_once()

    assert report.modified_positions == (100,)
    assert report.has_drift is True


def test_cancelled_and_opened_orders_detected(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()
    sync.poll_once()

    state["orders"] = (_order(ticket=600, type=4),)  # new buy stop

    report = sync.poll_once()

    assert report.cancelled_orders == (500,)
    assert report.opened_orders == (600,)


def test_balance_and_equity_deltas(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()
    sync.poll_once()

    state["account"] = _account(balance=100_025.0, equity=100_030.0)

    report = sync.poll_once()

    assert report.balance_delta == 25.0
    assert report.equity_delta == 20.0


# -- failure handling ------------------------------------------------------


def test_poll_failure_resets_connection_flag(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()
    sync.poll_once()
    assert sync._connected is True

    state["positions"] = None  # simulate dropout

    with pytest.raises(MT5SyncError):
        sync.poll_once()

    assert sync._connected is False  # next poll reconnects from scratch


# -- background worker -----------------------------------------------------


def test_run_bounds_iterations(fake_mt5):
    sync = _sync()

    sync.run(poll_interval=0, max_iterations=2)

    assert sync._prev is not None  # baseline established


def test_run_survives_transient_failure_and_recovers(fake_mt5):
    fake, state = fake_mt5
    sync = _sync()

    calls = {"n": 0}
    real_positions_get = state

    def _flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # first tick fails (e.g. IPC drop)
        return real_positions_get["positions"]

    fake.positions_get = _flaky

    # Must not raise: failure is logged, worker continues.
    sync.run(poll_interval=0, max_iterations=3)

    assert calls["n"] >= 3
    assert sync._prev is not None  # recovered and baselined


def test_on_change_fires_only_on_drift(fake_mt5):
    fake, state = fake_mt5
    seen = []
    sync = _sync(on_change=seen.append)

    # Poll 1: initial (no drift). Poll 2: new position (drift).
    calls = {"n": 0}
    base_positions = state["positions"]

    def _positions():
        calls["n"] += 1
        if calls["n"] <= 1:
            return base_positions
        return (_position(ticket=200),)

    fake.positions_get = _positions

    sync.run(poll_interval=0, max_iterations=3)

    # initial baseline skipped, exactly one drift report delivered
    assert len(seen) == 1
    assert seen[0].has_drift is True
    assert seen[0].opened_positions == (200,)


def test_on_change_exception_does_not_kill_worker(fake_mt5):
    def _bad_callback(report):
        raise RuntimeError("subscriber blew up")

    sync = _sync(on_change=_bad_callback)

    sync.run(poll_interval=0, max_iterations=2)  # must not raise

    assert sync._prev is not None


def test_start_background_and_stop(fake_mt5):
    sync = _sync(poll_interval=0.01)

    thread = sync.start_background()
    assert thread.is_alive()

    # Second call returns the same live thread.
    assert sync.start_background() is thread

    time.sleep(0.05)
    sync.stop(timeout=5.0)

    assert not thread.is_alive()


def test_stop_without_worker_is_safe(fake_mt5):
    _sync().stop()  # must not raise
