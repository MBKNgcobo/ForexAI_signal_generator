"""History Node: rolling-window Daily Strategic Bias gatekeeper."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app.schemas.strategy import StrategyObject, safe_mode_strategy
from app.services.history_store import HistoryStore
from app.services.technical_indicators import (
    calculate_atr,
    calculate_ema,
)

logger = logging.getLogger(__name__)

SHORT_WINDOW = "24h"
MED_WINDOW = "72h"
LONG_WINDOW = "120h"

VOL_EXPANSION_HIGH = 1.3
VOL_COMPRESSION_LOW = 0.85
EFF_TREND = 0.25
EFF_STRONG_TREND = 0.35
EFF_CHOP = 0.20
TREND_STRONG = 0.5


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def _parse_ts(raw: Any) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(raw))
    except Exception:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def compute_window_features(bars: list[dict]) -> dict:
    """Pure maths: rolling bars -> volatility/trend/structure features.

    Never raises on bad input; returns zero-features instead so the
    caller can fail closed to Safe Mode.
    """

    try:
        ordered = sorted(
            [b for b in bars if isinstance(b, dict)],
            key=lambda b: str(b.get("ts") or ""),
        )
    except Exception:
        return _empty_features(reason="unsortable bars")

    closes = [_safe_float(b.get("close")) for b in ordered]
    closes = [c for c in closes if c > 0]

    if len(ordered) < 2 or not closes:
        return _empty_features(reason="insufficient bars")

    candle_dicts = [
        {
            "high": _safe_float(b.get("high")),
            "low": _safe_float(b.get("low")),
            "close": _safe_float(b.get("close")),
        }
        for b in ordered
    ]

    atr = calculate_atr(candle_dicts, period=14)
    last_close = closes[-1]
    atr_pct = (atr / last_close) if atr and last_close > 0 else 0.0

    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)

    ema20_above_ema50 = (
        1 if ema20 is not None and ema50 is not None and ema20 > ema50 else 0
    )
    ema50_above_ema200 = (
        1 if ema50 is not None and ema200 is not None and ema50 > ema200 else 0
    )
    price_vs_ema50 = (
        (last_close / ema50 - 1.0) if ema50 else 0.0
    )
    sign = 1.0 if price_vs_ema50 > 0 else (-1.0 if price_vs_ema50 < 0 else 0.0)
    trend_score = (
        0.4 * float(ema50_above_ema200)
        + 0.3 * float(ema20_above_ema50)
        + 0.3 * sign
    )

    moves = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    total_move = sum(moves)
    net_move = abs(closes[-1] - closes[0])
    efficiency = (net_move / total_move) if total_move > 0 else 0.0

    highs = [_safe_float(b.get("high")) for b in ordered]
    lows = [_safe_float(b.get("low")) for b in ordered]
    window_high = max(highs) if highs else last_close
    window_low = min(lows) if lows else last_close
    window_range = window_high - window_low
    range_pos = (
        (last_close - window_low) / window_range if window_range > 0 else 0.5
    )

    mean = sum(closes) / len(closes)
    var = sum((c - mean) ** 2 for c in closes) / len(closes)
    rolling_vol = (var**0.5 / last_close) if last_close > 0 else 0.0

    gap_max = 0.0
    try:
        stamps = [_parse_ts(b.get("ts")) for b in ordered]
        stamps = [s for s in stamps if s is not None]
        gaps = [
            (later - earlier).total_seconds()
            for earlier, later in zip(stamps, stamps[1:])
        ]
        gap_max = max(gaps) if gaps else 0.0
    except Exception:
        gap_max = 0.0

    return {
        "bar_count": len(ordered),
        "atr": atr or 0.0,
        "atr_pct": atr_pct,
        "ema20_above_ema50": ema20_above_ema50,
        "ema50_above_ema200": ema50_above_ema200,
        "price_vs_ema50": price_vs_ema50,
        "trend_score": trend_score,
        "efficiency": efficiency,
        "range_pos": range_pos,
        "rolling_vol": rolling_vol,
        "high_low_range_pct": (
            window_range / last_close if last_close > 0 else 0.0
        ),
        "gap_max_sec": gap_max,
        "last_close": last_close,
        "ok": True,
        "reason": "",
    }


def _empty_features(reason: str) -> dict:
    return {
        "bar_count": 0,
        "atr": 0.0,
        "atr_pct": 0.0,
        "ema20_above_ema50": 0,
        "ema50_above_ema200": 0,
        "price_vs_ema50": 0.0,
        "trend_score": 0.0,
        "efficiency": 0.0,
        "range_pos": 0.5,
        "rolling_vol": 0.0,
        "high_low_range_pct": 0.0,
        "gap_max_sec": 0.0,
        "last_close": 0.0,
        "ok": False,
        "reason": reason,
    }


def classify_regime(
    short: dict,
    medium: dict,
    long_: dict,
) -> str:
    """Translate rolling windows into a regime label (pure)."""

    try:
        atr_short = _safe_float(short.get("atr_pct"))
        atr_long = _safe_float(long_.get("atr_pct"))
        vol_ratio = (atr_short / atr_long) if atr_long > 0 else 1.0
        eff = _safe_float(medium.get("efficiency", short.get("efficiency")))
        trend = abs(_safe_float(medium.get("trend_score", short.get("trend_score"))))

        if (
            vol_ratio > VOL_EXPANSION_HIGH
            and eff > EFF_STRONG_TREND
            and trend > TREND_STRONG
        ):
            return "HIGH_VOL_TREND"
        if vol_ratio > VOL_EXPANSION_HIGH and eff < EFF_CHOP:
            return "HIGH_VOL_CHOP"
        if vol_ratio < VOL_COMPRESSION_LOW and eff < EFF_CHOP:
            return "LOW_VOL_CHOP"
        if eff > EFF_TREND:
            return "NORMAL_TREND"
        if eff < EFF_CHOP:
            return "LOW_VOL_CHOP"
        return "NORMAL_TREND"
    except Exception:
        return "SAFE_MODE"


_MULTIPLIER_BY_REGIME = {
    "NORMAL_TREND": 1.0,
    "HIGH_VOL_TREND": 0.7,
    "HIGH_VOL_CHOP": 0.5,
    "LOW_VOL_CHOP": 0.5,
    "SAFE_MODE": 0.5,
}


def build_strategy(
    per_pair_windows: dict[str, dict[str, dict]],
    *,
    min_bars: int = 50,
    max_pairs: int = 4,
    now: datetime | None = None,
) -> StrategyObject:
    """Pure: per-pair window features -> advisory StrategyObject."""

    try:
        moment = now or datetime.now(timezone.utc)
        blocked: dict[str, str] = {}
        per_pair_regime: dict[str, str] = {}
        scored: list[tuple[float, str]] = []

        for symbol, windows in (per_pair_windows or {}).items():
            try:
                short = windows.get(SHORT_WINDOW) or {}
                medium = windows.get(MED_WINDOW) or {}
                long_ = windows.get(LONG_WINDOW) or {}

                bars = int(
                    _safe_float(
                        medium.get("bar_count", short.get("bar_count", 0))
                    )
                )
                if bars < min_bars:
                    blocked[symbol] = "INSUFFICIENT_BARS"
                    per_pair_regime[symbol] = "SAFE_MODE"
                    continue

                gap = _safe_float(
                    medium.get("gap_max_sec", short.get("gap_max_sec", 0.0))
                )
                if gap > 1.5 * 3600:
                    blocked[symbol] = "CANDLE_GAP"
                    per_pair_regime[symbol] = "SAFE_MODE"
                    continue

                regime = classify_regime(short, medium, long_)
                per_pair_regime[symbol] = regime

                eff = _safe_float(medium.get("efficiency", 0.0))
                if regime in ("HIGH_VOL_CHOP", "LOW_VOL_CHOP") and eff < 0.15:
                    blocked[symbol] = regime
                    continue

                atr_s = _safe_float(short.get("atr_pct", 0.0))
                atr_l = _safe_float(long_.get("atr_pct", 0.0))
                vol_ratio = (atr_s / atr_l) if atr_l > 0 else 1.0
                trend = abs(_safe_float(medium.get("trend_score", 0.0)))
                score = (
                    0.5 * trend
                    + 0.3 * eff
                    + 0.2 * min(vol_ratio, 2.0) / 2.0
                )
                scored.append((score, symbol))
            except Exception as exc:
                blocked[symbol] = f"CALC_ERROR:{type(exc).__name__}"
                per_pair_regime[symbol] = "SAFE_MODE"

        scored.sort(reverse=True)
        allowed = [s for _, s in scored[:max_pairs]]

        regimes = [per_pair_regime.get(s) for s in allowed]
        regimes = [r for r in regimes if r]
        if not regimes:
            global_regime = "SAFE_MODE" if blocked else "NORMAL_TREND"
        elif len(set(regimes)) == 1:
            global_regime = regimes[0]
        else:
            order = [
                "LOW_VOL_CHOP",
                "HIGH_VOL_CHOP",
                "SAFE_MODE",
                "HIGH_VOL_TREND",
                "NORMAL_TREND",
            ]
            global_regime = sorted(
                set(regimes), key=lambda r: order.index(r) if r in order else 99
            )[0]

        multiplier = _MULTIPLIER_BY_REGIME.get(global_regime, 0.5)
        covered = len(allowed)
        total = len(per_pair_windows or {})
        confidence = (covered / total) if total else 0.0

        return StrategyObject(
            allowed_pairs=allowed,
            blocked_pairs=blocked,
            regime=global_regime,
            regime_per_pair=per_pair_regime,
            volume_multiplier=multiplier,
            confidence=round(confidence, 4),
            computed_at=moment.isoformat(),
            source="history_node",
            reason=f"regime={global_regime} allowed={allowed}",
            stale=False,
        )
    except Exception as exc:
        return safe_mode_strategy(reason=f"Safe Mode: build failed ({exc}).")


def _record_history_outcome(result: str) -> None:
    try:
        from app.observability.metrics import HISTORY_REFRESH_TOTAL

        HISTORY_REFRESH_TOTAL.labels(result=result).inc()
    except Exception:
        pass


class HistoryNode:
    """Stateful gatekeeper: SQLite-backed, cached-mirror, fail-safe."""

    def __init__(
        self,
        store: HistoryStore | None = None,
        *,
        db_path: str = "data/history.db",
        timeframe: str = "OneHour",
        short_hours: int = 24,
        medium_hours: int = 72,
        long_hours: int = 120,
        min_bars: int = 50,
        max_pairs: int = 4,
        symbols: list[str] | None = None,
        provider: Callable[..., list[dict]] | None = None,
    ) -> None:
        self.store = store or HistoryStore(db_path)
        self.db_path = db_path
        self.timeframe = timeframe
        self.short_hours = short_hours
        self.medium_hours = medium_hours
        self.long_hours = long_hours
        self.min_bars = min_bars
        self.max_pairs = max_pairs
        self.symbols = list(symbols) if symbols else []
        self.provider = provider
        self._mirror: StrategyObject | None = None
        self._mirror_lock = threading.Lock()
        self._broken = False

    def initialise(self) -> StrategyObject:
        """Load snapshot mirror; never raises (Safe Mode on failure)."""

        try:
            self.store.initialise()
            data = self.store.load_snapshot()
            if data:
                strategy = StrategyObject.from_dict(data)
            else:
                strategy = safe_mode_strategy(
                    reason="Safe Mode: no snapshot yet.",
                    allowed_pairs=(list(self.symbols) or ["*"]),
                )
            with self._mirror_lock:
                self._mirror = strategy
            return strategy
        except Exception as exc:
            self._quarantine_if_corrupt(exc)
            fallback = safe_mode_strategy(
                reason=f"Safe Mode: init failed ({exc}).",
                allowed_pairs=(list(self.symbols) or ["*"]),
            )
            with self._mirror_lock:
                self._mirror = fallback
            _record_history_outcome("fallback")
            return fallback

    def get_strategy(self) -> StrategyObject:
        """Hot-path read (~1ms mirror, else single SELECT). May raise."""

        with self._mirror_lock:
            mirror = self._mirror

        if mirror is not None:
            return mirror

        data = self.store.load_snapshot()

        if not data:
            raise RuntimeError("no history snapshot available")

        strategy = StrategyObject.from_dict(data)

        with self._mirror_lock:
            self._mirror = strategy

        return strategy

    def get_strategy_safe(self) -> StrategyObject:
        """Hot-path read that never raises (Safe Mode on any error)."""

        try:
            return self.get_strategy()
        except Exception as exc:
            logger.error("HistoryNode read failed, Safe Mode: %s", exc)
            _record_history_outcome("fallback")
            return safe_mode_strategy(
                reason=f"Safe Mode: read failed ({exc}).",
                allowed_pairs=(list(self.symbols) or ["*"]),
            )

    def _quarantine_if_corrupt(self, exc: Exception) -> None:
        text = str(exc).lower()
        if "malform" in text or "corrupt" in text or "not a database" in text:
            try:
                from pathlib import Path
                import time

                src = Path(self.db_path)
                if src.exists():
                    dst = src.with_suffix(
                        f".corrupt.{int(time.time())}.db"
                    )
                    src.rename(dst)
                    logger.error(
                        "History DB quarantined %s -> %s",
                        src,
                        dst,
                    )
            except Exception as move_exc:
                logger.error("History quarantine failed: %s", move_exc)

    def refresh(
        self,
        *,
        now: datetime | None = None,
    ) -> StrategyObject:
        """Background recompute: delta fetch -> windows -> snapshot.

        Never raises: failures return Safe Mode and keep old snapshot.
        """

        moment = now or datetime.now(timezone.utc)
        try:
            self.store.initialise()
            if not self.symbols or self.provider is None:
                raise RuntimeError("history provider/symbols not configured")

            per_pair: dict[str, dict[str, dict]] = {}

            for symbol in self.symbols:
                try:
                    fresh = self._fetch_delta(symbol)
                    if fresh:
                        self.store.upsert_bars(fresh)
                except Exception as fetch_exc:
                    logger.warning(
                        "History fetch failed for %s: %s",
                        symbol,
                        fetch_exc,
                    )

                windows: dict[str, dict] = {}
                for name, hours in (
                    (SHORT_WINDOW, self.short_hours),
                    (MED_WINDOW, self.medium_hours),
                    (LONG_WINDOW, self.long_hours),
                ):
                    try:
                        bars = self.store.fetch_window_bars(
                            symbol,
                            self.timeframe,
                            lookback_hours=hours,
                            now=moment,
                        )
                        feats = compute_window_features(bars)
                        windows[name] = feats
                        self.store.save_window(symbol, name, feats)
                    except Exception as win_exc:
                        logger.warning(
                            "History window %s/%s failed: %s",
                            symbol,
                            name,
                            win_exc,
                        )
                        windows[name] = _empty_features(reason=str(win_exc))

                per_pair[symbol] = windows

            strategy = build_strategy(
                per_pair,
                min_bars=self.min_bars,
                max_pairs=self.max_pairs,
                now=moment,
            )
            self.store.save_snapshot(strategy.to_dict())
            with self._mirror_lock:
                self._mirror = strategy
            _record_history_outcome("ok")
            return strategy
        except Exception as exc:
            logger.error("HistoryNode refresh failed, Safe Mode: %s", exc)
            _record_history_outcome("error")
            fallback = safe_mode_strategy(
                reason=f"Safe Mode: refresh failed ({exc}).",
                allowed_pairs=(list(self.symbols) or ["*"]),
            )
            with self._mirror_lock:
                if self._mirror is None:
                    self._mirror = fallback
            return self._mirror

    def _fetch_delta(self, symbol: str) -> list[dict]:
        """Fetch only bars newer than the stored max ts (closed only)."""

        assert self.provider is not None
        latest = None
        try:
            latest = self.store.latest_ts(symbol, self.timeframe)
        except Exception:
            latest = None

        raw = self.provider(symbol, self.timeframe, latest) or []
        rows: list[dict] = []

        for bar in raw:
            try:
                ts_raw = bar.get("ts") or bar.get("timestamp")
                moment = _parse_ts(ts_raw)
                if moment is None:
                    continue
                high = _safe_float(bar.get("high"))
                low = _safe_float(bar.get("low"))
                close = _safe_float(bar.get("close"))
                open_ = _safe_float(bar.get("open"), close)
                if close <= 0 or high <= 0 or low <= 0:
                    continue
                prev_close = rows[-1]["close"] if rows else close
                tr_cap = 0.0
                true_range = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
                # Cap single-bar shock at 3x median TR so one news spike
                # cannot permanently flip the regime (F-5).
                if rows:
                    past = sorted(r["true_range"] for r in rows)
                    median = past[len(past) // 2]
                    if median > 0:
                        tr_cap = 3.0 * median
                        true_range = min(true_range, tr_cap)
                if true_range <= 0:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "timeframe": self.timeframe,
                        "ts": moment.isoformat(),
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": close,
                        "true_range": true_range,
                    }
                )
            except Exception:
                continue

        return rows


_node_singleton: HistoryNode | None = None
_node_lock = threading.Lock()


def get_history_node() -> HistoryNode:
    """Process-wide HistoryNode singleton (lazy, fail-safe)."""

    global _node_singleton

    with _node_lock:
        if _node_singleton is not None:
            return _node_singleton

        try:
            from app import config as app_config

            db_path = "data/history.db"
            short_h, med_h, long_h = 24, 72, 120
            min_bars, max_pairs = 50, 4
            symbols: list[str] = []

            try:
                db_path = str(app_config.history_db_path())
                short_h = int(app_config.history_short_hours())
                med_h = int(app_config.history_medium_hours())
                long_h = int(app_config.history_long_hours())
                min_bars = int(app_config.history_min_bars())
                max_pairs = int(app_config.history_max_pairs())
                symbols = list(app_config.history_symbols())
            except Exception:
                pass

            node = HistoryNode(
                db_path=db_path,
                short_hours=short_h,
                medium_hours=med_h,
                long_hours=long_h,
                min_bars=min_bars,
                max_pairs=max_pairs,
                symbols=symbols,
            )
        except Exception:
            node = HistoryNode()

        try:
            node.initialise()
        except Exception:
            pass

        _node_singleton = node
        return node


def run_history_gate(state: dict) -> dict:
    """LangGraph node: inject advisory history_context (never raises)."""

    try:
        strategy = get_history_node().get_strategy_safe()
    except Exception as exc:
        strategy = safe_mode_strategy(
            reason=f"Safe Mode: gate failed ({exc})."
        )

    try:
        return {"history_context": strategy.to_dict()}
    except Exception:
        return {
            "history_context": safe_mode_strategy(
                reason="Safe Mode: serialisation failed."
            ).to_dict()
        }





