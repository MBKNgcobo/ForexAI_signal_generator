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


@pytest.fixture(autouse=True)
def hermetic_environment(tmp_path, monkeypatch):
    """Guarantee the suite never reaches a live provider (SQA C-02).

    Two leaks made the suite non-hermetic and let a real API key reach a
    third-party endpoint (and the pytest logs):

    1. ``load_dotenv()`` at import time pulls the real ``TWELVE_DATA_API_KEY``
       (and other secrets) from ``.env`` into ``os.environ`` for the whole
       session.
    2. ``TestClient`` runs the app lifespan, which starts the background
       SL/TP monitor. That monitor polls the *real* ``data/signals.db``
       (leftover active signals) and builds the process-wide market-data
       singleton with whatever key is present - before a test's own
       ``delenv``/``monkeypatch`` runs. The subsequent route call reuses that
       cached provider, so a "missing key" test hit the live API with the real
       key instead of returning 503.

    This fixture neutralises both: real credentials are stripped, the signal
    store is isolated to a per-test temp file, the background monitor is
    disabled, and the shared market-data/signal singletons are reset so a
    provider built with a real key can never leak into the next test. Tests
    that need a key set their own via ``monkeypatch.setenv`` afterwards.
    """

    from app.api import signals as sig_api
    from app.config import signal_db_path, signal_monitor_enabled
    from app.services.market_data_provider_factory import (
        reset_shared_market_data_service,
    )

    # Isolate the signal store and disable the background monitor so no
    # lifespan-started worker can fire a provider call mid-test.
    monkeypatch.setenv("SIGNAL_DB_PATH", str(tmp_path / "signals.db"))
    monkeypatch.setenv("SIGNAL_MONITOR_ENABLED", "0")
    signal_db_path.cache_clear()
    signal_monitor_enabled.cache_clear()

    # Strip real provider credentials so no code path can reach a live API.
    for secret in (
        "TWELVE_DATA_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "SOTW_API_KEY",
        "BUSINESS_QUANT_API_KEY",
        "MT5_PASSWORD",
        "RAG_DB_PASSWORD",
    ):
        monkeypatch.delenv(secret, raising=False)

    # Drop any singleton built with a real key before the test runs.
    reset_shared_market_data_service()
    sig_api.reset_signal_tracking()

    yield

    reset_shared_market_data_service()
    sig_api.reset_signal_tracking()
    signal_db_path.cache_clear()
    signal_monitor_enabled.cache_clear()
