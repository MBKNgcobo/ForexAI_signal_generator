"""Accepted-signal tracking: acceptance, SL/TP, lifecycle, API (mock prices)."""

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def store(tmp_path):
    from app.services.signal_tracking.store import SignalStore

    s = SignalStore(str(tmp_path / "signals.db"))
    s.initialise()
    return s


def _long(**over):
    base = dict(
        symbol="EURUSD",
        direction="BUY",
        timeframe="FifteenMinutes",
        entry_price=1.1000,
        stop_loss=1.0900,
        take_profit=1.1150,
    )
    base.update(over)
    return base


def _short(**over):
    base = dict(
        symbol="GBPUSD",
        direction="SELL",
        timeframe="OneHour",
        entry_price=1.2500,
        stop_loss=1.2600,
        take_profit=1.2350,
    )
    base.update(over)
    return base


# -- acceptance + persistence ----------------------------------------------


def test_accept_valid_long_creates_one_record(store):
    sig, created = store.accept(**_long(signal_id="L1"))
    assert created is True
    assert sig.direction == "LONG"
    assert sig.status == "ACTIVE"
    assert len(store.list_signals()) == 1
    types = [e["event_type"] for e in store.events("L1")]
    assert types == ["SIGNAL_ACCEPTED", "SIGNAL_MONITORING_STARTED"]


def test_accept_valid_short_creates_one_record(store):
    sig, created = store.accept(**_short(signal_id="S1"))
    assert created is True
    assert sig.direction == "SHORT"


def test_invalid_sltp_relationships_rejected(store):
    with pytest.raises(ValueError, match="LONG"):
        store.accept(**_long(stop_loss=1.1100))  # SL above entry
    with pytest.raises(ValueError, match="LONG"):
        store.accept(**_long(take_profit=1.0900))  # TP below entry
    with pytest.raises(ValueError, match="SHORT"):
        store.accept(**_short(stop_loss=1.2400))
    with pytest.raises(ValueError, match="SHORT"):
        store.accept(**_short(take_profit=1.2600))
    with pytest.raises(ValueError, match="not executable"):
        store.accept(**_long(direction="HOLD"))
    with pytest.raises(ValueError, match="refusing to invent"):
        store.accept(**_long(entry_price=None))
    assert store.list_signals() == []


def test_duplicate_acceptance_no_duplicate(store):
    first, c1 = store.accept(**_long(signal_id="DUP"))
    second, c2 = store.accept(**_long(signal_id="DUP"))
    assert (c1, c2) == (True, False)
    assert first.signal_id == second.signal_id
    assert len(store.list_signals()) == 1
    assert len(store.events("DUP")) == 2


def test_signals_survive_reload(tmp_path):
    from app.services.signal_tracking.store import SignalStore

    db = str(tmp_path / "signals.db")

    first = SignalStore(db)
    first.initialise()
    sig, created = first.accept(**_long(signal_id="PERSIST"))
    assert created is True

    # A brand-new store instance over the same file (simulating a process
    # restart) must see the persisted signal and its audit events.
    reloaded = SignalStore(db)
    reloaded.initialise()
    fetched = reloaded.get("PERSIST")

    assert fetched is not None
    assert fetched.signal_id == sig.signal_id
    assert fetched.direction == "LONG"
    assert fetched.entry_price == sig.entry_price
    assert [e["event_type"] for e in reloaded.events("PERSIST")] == [
        "SIGNAL_ACCEPTED",
        "SIGNAL_MONITORING_STARTED",
    ]


# -- SL/TP detection (pure outcomes + monitor with mock fetcher) -----------


def test_outcome_long_tp_sl():
    from app.services.signal_tracking.outcomes import evaluate_outcome

    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11, price=1.12
    ) == "TP"
    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11, price=1.08
    ) == "SL"
    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11, price=1.10
    ) == "NONE"


def test_outcome_short_tp_sl():
    from app.services.signal_tracking.outcomes import evaluate_outcome

    assert evaluate_outcome(
        direction="SHORT", stop_loss=1.11, take_profit=1.09, price=1.08
    ) == "TP"
    assert evaluate_outcome(
        direction="SHORT", stop_loss=1.11, take_profit=1.09, price=1.12
    ) == "SL"


def test_outcome_bid_ask_convention():
    from app.services.signal_tracking.outcomes import evaluate_outcome

    # LONG TP needs the ask; LONG SL triggers on the bid.
    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11,
        bid=1.095, ask=1.11,
    ) == "TP"
    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11,
        bid=1.09, ask=1.10,
    ) == "SL"


def test_outcome_ambiguous_gap():
    from app.services.signal_tracking.outcomes import evaluate_outcome

    assert evaluate_outcome(
        direction="LONG", stop_loss=1.09, take_profit=1.11,
        candle_high=1.12, candle_low=1.08,
    ) == "AMBIGUOUS"


def _monitor(store, quote):
    from app.services.signal_tracking.monitor import SignalMonitor

    async def _fetch(_signal):
        return dict(quote)

    return SignalMonitor(store, price_fetcher=_fetch)


def test_monitor_long_reaches_tp(store):
    sig, _ = store.accept(**_long(signal_id="MTP"))
    mon = _monitor(store, {"price": 1.1160})
    status = asyncio.run(mon.check_signal(store.get("MTP")))
    assert status == "TAKE_PROFIT_HIT"
    done = store.get("MTP")
    assert done.status == "TAKE_PROFIT_HIT"
    assert done.close_price == 1.1160
    assert done.closed_at is not None


def test_monitor_long_reaches_sl(store):
    store.accept(**_long(signal_id="MSL"))
    mon = _monitor(store, {"price": 1.0890})
    assert asyncio.run(mon.check_signal(store.get("MSL"))) == "STOP_LOSS_HIT"


def test_monitor_short_tp_and_sl(store):
    store.accept(**_short(signal_id="STP"))
    assert asyncio.run(
        _monitor(store, {"price": 1.2340}).check_signal(store.get("STP"))
    ) == "TAKE_PROFIT_HIT"
    store.accept(**_short(signal_id="SSL"))
    assert asyncio.run(
        _monitor(store, {"price": 1.2610}).check_signal(store.get("SSL"))
    ) == "STOP_LOSS_HIT"


def test_monitor_mid_range_stays_active(store):
    store.accept(**_long(signal_id="MID"))
    mon = _monitor(store, {"price": 1.1050})
    assert asyncio.run(mon.check_signal(store.get("MID"))) is None
    assert store.get("MID").status == "ACTIVE"


def test_completed_signal_cannot_complete_twice(store):
    store.accept(**_long(signal_id="ONCE"))
    mon = _monitor(store, {"price": 1.1160})
    asyncio.run(mon.check_signal(store.get("ONCE")))
    tracked, done = store.complete(
        "ONCE", status="TAKE_PROFIT_HIT", close_price=1.12,
        event_type="TAKE_PROFIT_HIT",
    )
    assert done is False
    assert tracked.status == "TAKE_PROFIT_HIT"
    assert [e["event_type"] for e in store.events("ONCE")].count(
        "TAKE_PROFIT_HIT"
    ) == 1


def test_candle_bar_age_tolerated_but_truly_stale_rejected():
    """Regression: a valid bar open older than the fixed window must pass.

    A 15-minute candle timestamp is the bar OPEN, so a healthy feed is up to
    ~900 s old. The project's bar-age budget (``max_candle_age_seconds``) must
    govern, otherwise every valid candle is treated as stale and no outcome can
    ever be detected.
    """

    from datetime import datetime, timedelta, timezone

    from app.services.signal_tracking.quotes import validate_quote

    # 511 s old: beyond the default 300 s window, inside the 15-min bar budget.
    in_bar_budget = {
        "price": 1.11,
        "at": (datetime.now(timezone.utc) - timedelta(seconds=511)).isoformat(),
        "max_age_seconds": 1860.0,
    }
    assert validate_quote(in_bar_budget, stale_seconds=300.0) is not None

    # 3600 s old: beyond the 15-min bar budget, genuinely stale, must be rejected.
    beyond_budget = {
        "price": 1.11,
        "at": (datetime.now(timezone.utc) - timedelta(seconds=3600)).isoformat(),
        "max_age_seconds": 1860.0,
    }
    assert validate_quote(beyond_budget, stale_seconds=300.0) is None
    assert "_stale_age" in beyond_budget

    # No bar hint at all: the plain stale window governs.
    no_hint = {
        "price": 1.11,
        "at": (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat(),
    }
    assert validate_quote(no_hint, stale_seconds=300.0) is None


def test_stale_price_never_fabricates_hit(store):
    from datetime import datetime, timedelta, timezone

    from app.services.signal_tracking.monitor import SignalMonitor

    store.accept(**_long(signal_id="STALE"))

    async def _fetch(_signal):
        return {
            "price": 1.1160,
            "at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        }

    mon = SignalMonitor(store, stale_seconds=60.0, price_fetcher=_fetch)
    assert asyncio.run(mon.check_signal(store.get("STALE"))) is None
    assert store.get("STALE").status == "ACTIVE"
    assert any(
        e["event_type"] == "MONITORING_ERROR"
        for e in store.events("STALE")
    )


def test_missing_price_keeps_active(store):
    from app.services.signal_tracking.monitor import SignalMonitor

    store.accept(**_long(signal_id="NOPRICE"))

    async def _fetch(_signal):
        return {}

    mon = SignalMonitor(store, price_fetcher=_fetch)
    assert asyncio.run(mon.check_signal(store.get("NOPRICE"))) is None
    assert store.get("NOPRICE").status == "ACTIVE"


def test_ambiguous_gap_marks_unresolved(store):
    store.accept(**_long(signal_id="AMB"))
    mon = _monitor(
        store, {"price": 1.10, "high": 1.12, "low": 1.08}
    )
    status = asyncio.run(mon.check_signal(store.get("AMB")))
    assert status == "OUTCOME_UNRESOLVED"
    assert store.get("AMB").status == "OUTCOME_UNRESOLVED"

# -- UI + lifecycle (API, SSE, restart, disconnect) -------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.api.signals as sig_api
    import app.config as cfg

    monkeypatch.setenv("SIGNAL_DB_PATH", str(tmp_path / "api.db"))
    # Disable the background poll loop: it would call the live provider and
    # race the tests' explicit run_once(), making outcomes non-deterministic.
    monkeypatch.setenv("SIGNAL_MONITOR_ENABLED", "0")
    for name in ("signal_db_path", "signal_monitor_enabled"):
        try:
            getattr(cfg, name).cache_clear()
        except Exception:
            pass
    sig_api.reset_signal_tracking()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    sig_api.reset_signal_tracking()
    for name in ("signal_db_path", "signal_monitor_enabled"):
        try:
            getattr(cfg, name).cache_clear()
        except Exception:
            pass


def test_api_accept_lists_and_filters(client):
    r = client.post(
        "/signals/accept",
        json=dict(
            symbol="EURUSD", direction="BUY", entry_price=1.1,
            stop_loss=1.09, take_profit=1.115,
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    sid = body["signal"]["signal_id"]

    again = client.post(
        "/signals/accept",
        json=dict(
            signal_id=sid, symbol="EURUSD", direction="BUY",
            entry_price=1.1, stop_loss=1.09, take_profit=1.115,
        ),
    )
    assert again.json()["created"] is False

    listed = client.get("/signals?active_only=true").json()
    assert listed["count"] == 1

    detail = client.get(f"/signals/{sid}").json()
    assert detail["signal"]["is_active"] is True
    assert [e["event_type"] for e in detail["events"]][:2] == [
        "SIGNAL_ACCEPTED", "SIGNAL_MONITORING_STARTED",
    ]

    summary = client.get("/signals/summary").json()
    assert summary["total_accepted"] == 1 and summary["active"] == 1


def test_api_rejects_invalid_levels(client):
    r = client.post(
        "/signals/accept",
        json=dict(
            symbol="EURUSD", direction="LONG", entry_price=1.1,
            stop_loss=1.11, take_profit=1.115,
        ),
    )
    assert r.status_code == 422


# -- authorization (SQA C-09) ------------------------------------------------


@pytest.fixture
def api_key_guard(monkeypatch):
    """Enable the shared-secret guard and clear it again afterwards."""
    from app.config import expected_api_key

    monkeypatch.setenv("AI_SERVICE_API_KEY", "signals-guard-secret")
    expected_api_key.cache_clear()
    yield "signals-guard-secret"
    expected_api_key.cache_clear()


def test_accept_requires_api_key_when_guard_enabled(client, api_key_guard):
    """POST /signals/accept must not be an unauthenticated write path.

    Without a key it is 401 before any store write; a wrong key is also 401.
    """
    payload = dict(
        symbol="EURUSD", direction="BUY", entry_price=1.1,
        stop_loss=1.09, take_profit=1.115,
    )

    missing = client.post("/signals/accept", json=payload)
    assert missing.status_code == 401

    wrong = client.post(
        "/signals/accept", json=payload,
        headers={"X-API-Key": "wrong"},
    )
    assert wrong.status_code == 401

    # Nothing was persisted by the rejected attempts (auth header required
    # for the read too, since the guard is router-wide).
    listed = client.get(
        "/signals", headers={"X-API-Key": api_key_guard}
    )
    assert listed.json()["count"] == 0


def test_accept_allows_valid_api_key(client, api_key_guard):
    r = client.post(
        "/signals/accept",
        json=dict(
            symbol="EURUSD", direction="BUY", entry_price=1.1,
            stop_loss=1.09, take_profit=1.115,
        ),
        headers={"X-API-Key": api_key_guard},
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True


def test_accept_analysis_requires_api_key_when_guard_enabled(
    client, api_key_guard,
):
    """The pipeline-vocabulary alias sits behind the same router guard."""
    r = client.post("/signals/accept-analysis", json={})
    assert r.status_code == 401


def test_api_completed_transition_visible(client, monkeypatch):
    from app.api import signals as sig_api

    r = client.post(
        "/signals/accept",
        json=dict(
            symbol="EURUSD", direction="LONG", entry_price=1.1,
            stop_loss=1.09, take_profit=1.115,
        ),
    )
    sid = r.json()["signal"]["signal_id"]
    mon = sig_api.get_monitor()

    async def _tp(_signal):
        return {"price": 1.12}

    mon._price_fetcher = _tp
    asyncio.run(mon.run_once())
    mon._price_fetcher = None

    done = client.get(f"/signals/{sid}").json()
    assert done["signal"]["status"] == "TAKE_PROFIT_HIT"
    assert done["signal"]["close_price"] == 1.12
    history = client.get("/signals?completed_only=true").json()
    assert history["count"] == 1
    summary = client.get("/signals/summary").json()
    assert summary["take_profit_hits"] == 1


def test_sse_receives_accept_event(client):
    """The SSE pub/sub delivers accept events without manual refresh."""
    import asyncio as _asyncio

    from app.services.signal_tracking.quotes import (
        publish,
        subscribe,
        unsubscribe,
    )

    async def _flow():
        queue = subscribe()
        try:
            await publish({"type": "PING", "marker": "sse-test"})
            ping = await _asyncio.wait_for(queue.get(), timeout=5.0)
            assert ping["type"] == "PING"
            # Simulate what POST /signals/accept publishes.
            await publish({"type": "SIGNAL_ACCEPTED", "signal_id": "X"})
            got = await _asyncio.wait_for(queue.get(), timeout=5.0)
            return got
        finally:
            unsubscribe(queue)

    received = _asyncio.run(_flow())
    assert received["type"] == "SIGNAL_ACCEPTED"


def test_restart_restores_history(tmp_path, monkeypatch):
    import app.api.signals as sig_api
    import app.config as cfg

    path = str(tmp_path / "restart.db")
    monkeypatch.setenv("SIGNAL_DB_PATH", path)
    cfg.signal_db_path.cache_clear()
    sig_api.reset_signal_tracking()
    from app.main import app

    with TestClient(app) as first:
        r = first.post(
            "/signals/accept",
            json=dict(
                symbol="EURUSD", direction="LONG", entry_price=1.1,
                stop_loss=1.09, take_profit=1.115,
            ),
        )
        assert r.status_code == 200
    sig_api.reset_signal_tracking()  # simulate process restart
    with TestClient(app) as second:
        listed = second.get("/signals").json()
        assert listed["count"] == 1
    sig_api.reset_signal_tracking()
    cfg.signal_db_path.cache_clear()


def test_disconnect_surfaced_and_recovery(client, monkeypatch):
    """A provider outage must surface, not fabricate a hit or lose the signal."""

    import app.services.signal_tracking.monitor as monitor_mod

    async def _boom(_signal, *, provider_name=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(monitor_mod, "fetch_quote", _boom)
    r = client.post(
        "/signals/accept",
        json=dict(
            symbol="EURUSD", direction="LONG", entry_price=1.1,
            stop_loss=1.09, take_profit=1.115,
        ),
    )
    sid = r.json()["signal"]["signal_id"]
    from app.api import signals as sig_api

    mon = sig_api.get_monitor()
    mon._price_fetcher = None
    report = asyncio.run(mon.run_once())

    # The failure is recorded and the signal is NOT completed.
    assert report["errors"] >= 1
    assert client.get(f"/signals/{sid}").json()["signal"]["status"] == "ACTIVE"

    # Health must report the disconnection instead of claiming a live price.
    health = client.get("/signals/health").json()
    assert health["provider_connected"] is False
    assert health["provider_error"]

    # Recovery: a valid quote drives the signal to its outcome.
    async def _tp(_signal, *, provider_name=None):
        return {"price": 1.12, "at": None}

    monkeypatch.setattr(monitor_mod, "fetch_quote", _tp)
    asyncio.run(mon.run_once())
    assert client.get(f"/signals/{sid}").json()["signal"]["status"] == "TAKE_PROFIT_HIT"
    assert client.get("/signals/health").json()["provider_connected"] is True

