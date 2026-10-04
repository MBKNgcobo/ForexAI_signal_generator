"""Per-source confidence calibration.

Raw specialist confidences (LLM self-reports, ensemble probabilities) are
uncalibrated: a reported 0.72 does not mean "right 72% of the time". This
module maps raw confidences to calibrated ones via small, auditable
piecewise-linear tables stored in ``models/calibration.json``.

Design notes:
- Pure stdlib, no new ML dependency; the table is data, regenerable from
  ``app/backtesting/threshold_analysis.py`` output.
- Missing file / unknown source / malformed input degrades to the identity
  map (raw value clamped to [0, 1]) rather than crashing the request path.
- ``raw_confidence`` is preserved alongside so the dashboard and auditors
  can see what the model said before calibration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CALIBRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "models"
    / "calibration.json"
)

# Sources with a registered calibration table. Anything else calibrates to
# the identity map so a new specialist cannot break the request path.
KNOWN_SOURCES = (
    "technical",
    "fundamental",
    "quant",
)


@dataclass(frozen=True)
class Calibration:
    """Piecewise-linear raw -> calibrated maps, one per source."""

    tables: dict[str, list[tuple[float, float]]] = field(default_factory=dict)

    def calibrate(self, value: Any, source: str) -> float:
        """Map a raw confidence to its calibrated value in [0, 1]."""

        try:
            raw = float(value)
        except (TypeError, ValueError):
            return 0.0

        if raw != raw:  # NaN guard without importing math at module scope.
            return 0.0

        raw = min(1.0, max(0.0, raw))

        points = self.tables.get(source)

        if not points:
            return raw

        return _interpolate(raw, points)


def _interpolate(raw: float, points: list[tuple[float, float]]) -> float:
    """Linear interpolation over sorted (raw, calibrated) control points."""

    first_raw, first_cal = points[0]
    last_raw, last_cal = points[-1]

    if raw <= first_raw:
        return min(1.0, max(0.0, first_cal))

    if raw >= last_raw:
        return min(1.0, max(0.0, last_cal))

    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= raw <= x1:
            span = x1 - x0

            if span <= 0:
                return min(1.0, max(0.0, y1))

            ratio = (raw - x0) / span
            calibrated = y0 + ratio * (y1 - y0)

            return min(1.0, max(0.0, calibrated))

    return min(1.0, max(0.0, last_cal))


def _parse_table(raw_points: Any) -> list[tuple[float, float]] | None:
    """Validate a control-point list; None when unusable."""

    if not isinstance(raw_points, list) or len(raw_points) < 2:
        return None

    parsed: list[tuple[float, float]] = []

    for entry in raw_points:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return None

        try:
            x = float(entry[0])
            y = float(entry[1])
        except (TypeError, ValueError):
            return None

        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return None

        parsed.append((x, y))

    parsed.sort(key=lambda point: point[0])

    return parsed


def load_calibration(path: str | Path | None = None) -> Calibration:
    """Load calibration tables from JSON; identity fallback on any problem."""

    resolved = Path(path) if path else DEFAULT_CALIBRATION_PATH

    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug(
            "Calibration file unavailable (%s); using identity map: %s",
            resolved,
            exc,
        )
        return Calibration()

    if not isinstance(payload, dict):
        logger.warning(
            "Ignoring calibration file %s: top-level JSON is not an object.",
            resolved,
        )
        return Calibration()

    tables: dict[str, list[tuple[float, float]]] = {}
    sources = payload.get("sources", payload)

    if not isinstance(sources, dict):
        return Calibration()

    for source in KNOWN_SOURCES:
        table = _parse_table(sources.get(source))

        if table is None:
            if source in sources:
                logger.warning(
                    "Ignoring malformed calibration table for %r in %s.",
                    source,
                    resolved,
                )
            continue

        tables[source] = table

    return Calibration(tables=tables)


@lru_cache(maxsize=1)
def get_calibration() -> Calibration:
    """Process-wide calibration singleton (clear via ``cache_clear``)."""

    return load_calibration()


def calibrate_confidence(value: Any, source: str) -> float:
    """Calibrate one confidence value using the process-wide tables."""

    return get_calibration().calibrate(value, source)
