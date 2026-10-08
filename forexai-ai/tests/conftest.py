"""Shared pytest configuration.

The suite lives in ``tests/`` without an ``__init__.py``, so pytest's default
import mode would only put ``tests/`` on ``sys.path`` - which breaks imports
such as ``from tests.fakes.fake_llm import ...``. ``pyproject.toml`` already
sets ``pythonpath = ["."]``; this explicit guard keeps the suite working even
if it is run with an older pytest that ignores that setting.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_trade_log(tmp_path, monkeypatch):
    """Point the JSONL trade log at a per-test temp file.

    ``SignalBridge.prepare()``/``execute()`` append ``order_sent``/``filled``
    audit events while exercising the pipeline; without this redirect the
    suite would pollute the real ``data/trade_log.jsonl`` the dashboard reads.
    ``trade_log_path()`` is lru-cached, so its cache is cleared around each
    test to pick up (and then forget) the temporary path.
    """

    from app.config import trade_log_path

    monkeypatch.setenv("TRADE_LOG_PATH", str(tmp_path / "trade_log.jsonl"))
    trade_log_path.cache_clear()
    yield
    trade_log_path.cache_clear()
