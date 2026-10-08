"""History Node: rolling windows, regimes, Safe Mode, gatekeeper."""

from datetime import datetime, timedelta, timezone

from app.services.history_node import (
    HistoryNode,
    build_strategy,
    classify_regime,
    compute_window_features,
    run_history_gate,
)
from app.services.history_store import HistoryStore


def _bars(
    n=80,
    start=1.1000,
    step=0.0005,
    start_time=None,
    gap_at=None,
    gap_hours=0.0,
):
    moment = start_time or (
        datetime.now(timezone.utc) - timedelta(hours=n)
    )
    rows = []
    for i in range(n):
        ts = moment + timedelta(hours=i)
        if gap_at is not None and i >= gap_at:
            ts = ts + timedelta(hours=gap_hours)
        price = start + step * i
        rows.append(
            {
                "symbol": "EURUSD",
                "timeframe": "OneHour",
                "ts": ts.isoformat(),
                "open": price - 0.0001,
                "high": price + 0.0004,
                "low": price - 0.0004,
                "close": price,
                "true_range": 0.0008,
            }
        )
    return rows


def test_window_features_trend_and_chop():
    trend = _bars(n=80, step=0.0005)
    feats = compute_window_features(trend)
    assert feats["ok"] is True
    assert feats["bar_count"] == 80
    assert feats["efficiency"] > 0.25
    assert feats["trend_score"] > 0

    chop_prices = [1.1 + (0.0003 if i % 2 == 0 else -0.0003) for i in range(80)]
    moment = datetime.now(timezone.utc) - timedelta(hours=80)
    chop = [
        {
            "ts": (moment + timedelta(hours=i)).isoformat(),
            "open": p,
            "high": p + 0.0004,
            "low": p - 0.0004,
            "close": p,
        }
        for i, p in enumerate(chop_prices)
    ]
    chop_feats = compute_window_features(chop)
    assert chop_feats["efficiency"] < feats["efficiency"]


def test_regime_table_and_multiplier():
    base = {
        "bar_count": 100,
        "trend_score": 0.8,
        "efficiency": 0.5,
        "atr_pct": 0.001,
        "gap_max_sec": 3600.0,
    }
    hot = dict(base, atr_pct=0.002)
    assert classify_regime(hot, base, base) == "HIGH_VOL_TREND"
    calm = dict(base, efficiency=0.05)
    assert classify_regime(base, calm, base) == "LOW_VOL_CHOP"
    strat = build_strategy(
        {"EURUSD": {"24h": hot, "72h": base, "120h": base}},
        min_bars=10,
    )
    assert strat.regime == "HIGH_VOL_TREND"
    assert strat.volume_multiplier == 0.7
    assert strat.allowed_pairs == ["EURUSD"]


def test_safe_mode_defaults():
    from app.schemas.strategy import safe_mode_strategy

    safe = safe_mode_strategy()
    assert safe.volume_multiplier == 0.5
    assert safe.regime == "SAFE_MODE"
    assert safe.is_pair_allowed("EURUSD") is True


def test_store_roundtrip_and_rolling_window(tmp_path):
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    store = HistoryStore(str(tmp_path / "h.db"))
    store.initialise()
    rows = _bars(n=130)
    assert store.upsert_bars(rows) == 130
    now = _dt.now(_tz.utc)
    short = store.fetch_window_bars(
        "EURUSD", "OneHour", lookback_hours=24, now=now
    )
    long_ = store.fetch_window_bars(
        "EURUSD", "OneHour", lookback_hours=120, now=now
    )
    assert 20 <= len(short) <= 26
    assert len(long_) > len(short)
    assert store.latest_ts("EURUSD", "OneHour") == rows[-1]["ts"]


def test_node_init_missing_db_returns_safe_mode(tmp_path):
    node = HistoryNode(
        db_path=str(tmp_path / "missing" / "h.db"),
        symbols=["EURUSD"],
    )
    strategy = node.initialise()
    assert strategy.regime == "SAFE_MODE"
    assert strategy.volume_multiplier == 0.5


def test_node_corrupt_db_safe_modes(tmp_path):
    db_path = tmp_path / "h.db"
    db_path.write_bytes(b"not a sqlite file")
    node = HistoryNode(db_path=str(db_path), symbols=["EURUSD"])
    strategy = node.initialise()
    assert strategy.regime == "SAFE_MODE"
    assert strategy.volume_multiplier == 0.5


def test_refresh_with_fake_provider_and_gap_blocks_pair(tmp_path):
    good = _bars(
        n=130,
        start_time=datetime.now(timezone.utc) - timedelta(hours=130),
    )
    gapped = _bars(
        n=130,
        start_time=datetime.now(timezone.utc) - timedelta(hours=130),
        gap_at=65,
        gap_hours=30,
    )

    def provider(symbol, timeframe, latest):
        assert timeframe == "OneHour"
        return gapped if symbol == "EURUSD" else good

    node = HistoryNode(
        db_path=str(tmp_path / "h.db"),
        symbols=["EURUSD", "GBPUSD"],
        provider=provider,
        min_bars=10,
    )
    node.initialise()
    strategy = node.refresh()
    assert "EURUSD" in strategy.blocked_pairs


def test_missing_bars_blocks_pair():
    thin = {
        "bar_count": 3,
        "trend_score": 0.9,
        "efficiency": 0.9,
        "atr_pct": 0.001,
        "gap_max_sec": 0.0,
    }
    rich = {
        "bar_count": 100,
        "trend_score": 0.9,
        "efficiency": 0.9,
        "atr_pct": 0.001,
        "gap_max_sec": 0.0,
    }
    strat = build_strategy(
        {
            "EURUSD": {"24h": thin, "72h": thin, "120h": thin},
            "GBPUSD": {"24h": rich, "72h": rich, "120h": rich},
        },
        min_bars=50,
    )
    assert "EURUSD" not in strat.allowed_pairs
    assert strat.blocked_pairs["EURUSD"] == "INSUFFICIENT_BARS"
    assert "GBPUSD" in strat.allowed_pairs


def _payload(symbol="EURUSD"):
    return {
        "symbol": symbol,
        "timeframe": "FifteenMinutes",
        "final_decision": {
            "direction": "BUY",
            "confidence": 0.8,
            "reasoning": "t",
        },
        "risk_assessment": {
            "approved": True,
            "entry_price": 1.1001,
            "stop_loss": 1.0951,
            "take_profit": 1.1076,
        },
    }


def test_bridge_blocks_and_scales_volume():
    from app.broker.signal_bridge import SignalRejectedError
    from app.broker.signal_bridge import prepare_order_request as prep
    from app.schemas.strategy import safe_mode_strategy as _safe

    blocked = {
        "allowed_pairs": ["GBPUSD"],
        "blocked_pairs": {"EURUSD": "LOW_VOL_CHOP"},
        "volume_multiplier": 0.7,
    }
    try:
        prep(_payload("EURUSD"), volume=0.02, history_strategy=blocked)
        raise AssertionError("should have rejected")
    except SignalRejectedError as exc:
        assert "HistoryNode blocks EURUSD" in str(exc)

    req = prep(_payload("GBPUSD"), volume=0.02, history_strategy=blocked)
    assert abs(req.volume - 0.014) < 1e-9

    safe = _safe(allowed_pairs=["*"])
    req2 = prep(_payload("EURUSD"), volume=0.02, history_strategy=safe)
    assert abs(req2.volume - 0.01) < 1e-9

    req3 = prep(_payload("EURUSD"), volume=0.02, history_strategy=None)
    assert req3.volume == 0.02


def _risk_state(**over):
    base = {
        "symbol": "EURUSD",
        "technical_analysis": {
            "direction": "BUY",
            "current_price": 1.1,
            "atr": 0.002,
        },
        "fundamental_analysis": {"direction": "BUY"},
        "quant_prediction": {
            "direction": "BUY",
            "probability": 0.8,
            "probabilities": {"BUY": 0.8, "SELL": 0.1},
            "model_agreement": 0.9,
        },
    }
    base.update(over)
    return base


def test_risk_agent_history_veto_and_multiplier():
    from app.agents.risk_agent import run_risk_agent

    blocked_ctx = {
        "allowed_pairs": ["GBPUSD"],
        "blocked_pairs": {"EURUSD": "LOW_VOL_CHOP"},
        "volume_multiplier": 0.5,
    }
    out = run_risk_agent(_risk_state(history_context=blocked_ctx))
    assert out["risk_assessment"]["approved"] is False

    ok_ctx = {
        "allowed_pairs": ["EURUSD"],
        "blocked_pairs": {},
        "volume_multiplier": 0.7,
    }
    out2 = run_risk_agent(_risk_state(history_context=ok_ctx))
    assert out2["risk_assessment"]["approved"] is True
    assert out2["risk_assessment"]["history_volume_multiplier"] == 0.7


def test_history_gate_never_raises(monkeypatch):
    import app.services.history_node as hn

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(hn, "get_history_node", _boom)
    out = run_history_gate({})
    assert out["history_context"]["regime"] == "SAFE_MODE"
    assert out["history_context"]["volume_multiplier"] == 0.5


def test_hot_path_never_calls_provider(tmp_path):
    calls: list = []

    def provider(symbol, timeframe, latest):
        calls.append(symbol)
        return []

    node = HistoryNode(
        db_path=str(tmp_path / "h.db"),
        symbols=["EURUSD"],
        provider=provider,
    )
    node.initialise()
    node.get_strategy_safe()
    assert calls == []


