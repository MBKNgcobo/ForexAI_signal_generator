"""Daily Strategic Bias strategy object (History Node output).

The History Node acts as a gatekeeper/filter layer: it never forces a
specific trade, it only publishes an advisory ``StrategyObject`` that the
intraday engine must query before executing a signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field


#: Regimes the History Node can publish (plus SAFE_MODE fallback).
REGIMES = frozenset(
    {
        "HIGH_VOL_TREND",
        "NORMAL_TREND",
        "HIGH_VOL_CHOP",
        "LOW_VOL_CHOP",
        "SAFE_MODE",
    }
)


@dataclass
class StrategyObject:
    """Advisory strategy gate for the intraday execution engine."""

    allowed_pairs: list[str] = field(
        default_factory=list
    )
    blocked_pairs: dict[str, str] = field(
        default_factory=dict
    )
    regime: str = "SAFE_MODE"
    regime_per_pair: dict[str, str] = field(
        default_factory=dict
    )
    volume_multiplier: float = 0.5
    confidence: float = 0.0
    computed_at: str = ""
    source: str = "safe_mode_fallback"
    reason: str = "Safe Mode: history unavailable."
    stale: bool = True

    def to_dict(self) -> dict:
        """JSON-safe representation for graph state / HTTP responses."""

        return {
            "allowed_pairs": list(self.allowed_pairs),
            "blocked_pairs": dict(self.blocked_pairs),
            "regime": self.regime,
            "regime_per_pair": dict(self.regime_per_pair),
            "volume_multiplier": float(self.volume_multiplier),
            "confidence": float(self.confidence),
            "computed_at": self.computed_at,
            "source": self.source,
            "reason": self.reason,
            "stale": bool(self.stale),
        }

    def is_pair_allowed(self, symbol: str) -> bool:
        """True when ``symbol`` may be traded under this strategy."""

        if not self.allowed_pairs:
            return False

        if "*" in self.allowed_pairs:
            return symbol not in self.blocked_pairs

        return symbol in self.allowed_pairs

    @classmethod
    def from_dict(cls, payload: dict) -> "StrategyObject":
        """Rebuild from a persisted dict (never raises on bad input)."""

        try:
            data = dict(payload or {})
        except Exception:
            return safe_mode_strategy(reason="Safe Mode: corrupt snapshot.")

        try:
            multiplier = float(data.get("volume_multiplier", 0.5))
        except (TypeError, ValueError):
            multiplier = 0.5

        multiplier = min(1.0, max(0.25, multiplier))

        regime = str(data.get("regime") or "SAFE_MODE")

        if regime not in REGIMES:
            regime = "SAFE_MODE"

        allowed = data.get("allowed_pairs") or []

        try:
            allowed_pairs = [str(p) for p in list(allowed)]
        except Exception:
            allowed_pairs = ["*"]

        blocked = data.get("blocked_pairs") or {}

        try:
            blocked_pairs = {
                str(k): str(v) for k, v in dict(blocked).items()
            }
        except Exception:
            blocked_pairs = {}

        per_pair = data.get("regime_per_pair") or {}

        try:
            regime_per_pair = {
                str(k): str(v) for k, v in dict(per_pair).items()
            }
        except Exception:
            regime_per_pair = {}

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        return cls(
            allowed_pairs=allowed_pairs,
            blocked_pairs=blocked_pairs,
            regime=regime,
            regime_per_pair=regime_per_pair,
            volume_multiplier=multiplier,
            confidence=min(1.0, max(0.0, confidence)),
            computed_at=str(data.get("computed_at") or ""),
            source=str(data.get("source") or "safe_mode_fallback"),
            reason=str(data.get("reason") or "Safe Mode."),
            stale=bool(data.get("stale", True)),
        )


def safe_mode_strategy(
    reason: str = "Safe Mode: history unavailable.",
    allowed_pairs: list[str] | None = None,
) -> StrategyObject:
    """Strict fallback: allow all (or given) pairs at half size.

    Never raises. The system must never halt live execution because a
    history calculation failed.
    """

    return StrategyObject(
        allowed_pairs=list(allowed_pairs) if allowed_pairs is not None else ["*"],
        blocked_pairs={},
        regime="SAFE_MODE",
        regime_per_pair={},
        volume_multiplier=0.5,
        confidence=0.0,
        computed_at="",
        source="safe_mode_fallback",
        reason=reason,
        stale=True,
    )
