"""Per-source confidence calibration: tables, fallback, bounds.

The calibration tables are data (models/calibration.json), so these tests
pin the mapping contract without touching artifacts or the network.
"""

import json

import pytest

from app.services.confidence_calibration import (
    Calibration,
    calibrate_confidence,
    get_calibration,
    load_calibration,
)


def _write_tables(tmp_path, sources: dict) -> str:
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps({"version": 1, "sources": sources}),
        encoding="utf-8",
    )
    return str(path)


def test_identity_fallback_when_file_missing(tmp_path):
    calibration = load_calibration(tmp_path / "does-not-exist.json")

    assert calibration.calibrate(0.72, "technical") == 0.72
    assert calibration.calibrate(0.72, "unknown-source") == 0.72


def test_monotone_mapping_and_clamping():
    calibration = Calibration(
        tables={
            "technical": [(0.0, 0.0), (0.5, 0.5), (1.0, 0.85)],
        }
    )

    assert calibration.calibrate(0.25, "technical") == pytest.approx(0.25)
    assert calibration.calibrate(0.75, "technical") == pytest.approx(0.675)
    assert calibration.calibrate(1.0, "technical") == pytest.approx(0.85)
    assert calibration.calibrate(2.5, "technical") == pytest.approx(0.85)
    assert calibration.calibrate(-1.0, "technical") == pytest.approx(0.0)


def test_unknown_source_is_identity():
    calibration = Calibration(
        tables={"technical": [(0.0, 0.0), (1.0, 0.9)]}
    )

    assert calibration.calibrate(0.8, "brand-new-agent") == 0.8


def test_malformed_table_falls_back_to_identity(tmp_path):
    path = _write_tables(tmp_path, {"technical": [["bad"]]})
    calibration = load_calibration(path)

    assert calibration.calibrate(0.8, "technical") == 0.8


def test_non_numeric_input_returns_zero():
    calibration = Calibration()

    assert calibration.calibrate(None, "technical") == 0.0
    assert calibration.calibrate("nope", "technical") == 0.0
    assert calibration.calibrate(float("nan"), "technical") == 0.0


def test_shipped_artifact_calibrates_downward():
    get_calibration.cache_clear()

    try:
        # LLM/ensemble confidences skew overconfident; the shipped prior
        # shrinks extremes toward the middle.
        assert get_calibration().calibrate(0.85, "technical") < 0.85
        assert calibrate_confidence(0.9, "quant") < 0.9
    finally:
        get_calibration.cache_clear()
