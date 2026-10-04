"""MT5 market-data provider (Phase 2): hermetic, no terminal required."""

import sys
import types
from datetime import datetime, timezone

import pytest

from app.broker import mt5_market_data_provider as mod
from app.broker.mt5_connection import MT5ConnectionError
from app.broker.mt5_market_data_provider import (
    MT5DataError,
    MT5MarketDataProvider,
)

# Three well-formed, oldest-first rate rows (MT5 returns ascending).
RATES = [
    {
        "time": 1_700_000_000,
        "open": 1.1000,
        "high": 1.1020,
        "low": 1.0990,
        "close": 1.1010,
        "tick_volume": 100,
    },
    {
        "time": 1_700_000_300,
        "open": 1.1010,
        "high": 1.1030,
        "low": 1.1000,
        "close": 1.1025,
        "tick_volume": 120,
    },
    {
        "time": 1_700_000_600,
        "open": 1.1025,
        "high": 1.1040,
        "low": 1.1015,
        "close": 1.1035,
        "tick_volume": 90,
    },
]

BOOK = [
    types.SimpleNamespace(type=1, price=1.1010, volume=10),  # buy
    types.SimpleNamespace(type=0, price=1.1008, volume=7),   # sell
]


def _make_fake_mt5(**overrides):
    """Build a fake MetaTrader5 module; returns (fake, calls)."""

    calls = {"symbols_get": 0, "select": [], "book_add": 0}
    symbol_candidates = overrides.pop("symbols_get", lambda p: [])

    def _symbols_get(pattern):
        calls["symbols_get"] += 1
        return symbol_candidates(pattern)

    defaults = {
        "TIMEFRAME_M1": 1,
        "TIMEFRAME_M5": 5,
        "TIMEFRAME_M15": 15,
        "TIMEFRAME_H1": 60,
        "TIMEFRAME_H4": 240,
        "TIMEFRAME_D1": 1440,
        "BOOK_TYPE_BUY": 1,
        "BOOK_TYPE_BUY_MARKET": 3,
        "symbol_info": lambda s: types.SimpleNamespace(name=s),
        "symbols_get": _symbols_get,
        "symbol_select": lambda s, f: calls["select"].append(s) or True,
        "copy_rates_from_pos": lambda s, tf, st, cnt: RATES,
        "symbol_info_tick": lambda s: types.SimpleNamespace(
            time=1_700_000_600, bid=1.1033, ask=1.1035, last=1.1034,
            volume=42,
        ),
        "market_book_get": lambda s: BOOK,
        "market_book_add": lambda s: (
            calls.__setitem__("book_add", calls["book_add"] + 1) or True
        ),
        "last_error": lambda: (10004, "no history"),
    }
    defaults.update(overrides)

    return types.SimpleNamespace(**defaults), calls


@pytest.fixture
def fake_mt5(monkeypatch):
    """Inject the fake package; neutralize terminal connect/shutdown."""

    return _install(monkeypatch)


def _install(monkeypatch, **overrides):
    fake, calls = _make_fake_mt5(**overrides)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(mod, "connect", lambda **kw: None)
    monkeypatch.setattr(mod, "shutdown", lambda: None)
    return fake, calls


def _provider() -> MT5MarketDataProvider:
    return MT5MarketDataProvider(
        login=12345, password="pw", server="Demo-Server"
    )


async def test_get_market_data_success(fake_mt5):
    provider = _provider()

    data = await provider.get_market_data(
        symbol="EURUSD", timeframe="FiveMinutes", limit=3
    )

    assert data.symbol == "EURUSD"
    assert data.timeframe == "FiveMinutes"
    assert len(data.candles) == 3

    first = data.candles[0]
    expected = datetime.fromtimestamp(
        1_700_000_000, tz=timezone.utc
    )

    assert first.timestamp == expected
    assert first.timestamp.tzinfo is not None
    assert first.volume == 100.0

    # Strictly ascending, enforced by the schema validator.
    stamps = [c.timestamp for c in data.candles]
    assert stamps == sorted(stamps)


def test_provider_construction_does_not_import_mt5(monkeypatch):
    """Lazy-integrity guard: ctor must not import MetaTrader5."""

    monkeypatch.delitem(sys.modules, "MetaTrader5", raising=False)
    _provider()

    assert "MetaTrader5" not in sys.modules


async def test_exact_symbol_skips_suffix_lookup(fake_mt5):
    _, calls = fake_mt5
    provider = _provider()

    await provider.get_market_data(
        symbol="EURUSD", timeframe="FiveMinutes"
    )

    # symbol_info matched exactly -> no symbols_get sweep needed.
    assert calls["symbols_get"] == 0


async def test_suffix_symbol_resolved_to_shortest(monkeypatch):
    _, calls = _install(
        monkeypatch,
        symbol_info=lambda s: None,
        symbols_get=lambda p: [
            types.SimpleNamespace(name="EURUSD.m"),
            types.SimpleNamespace(name="EURUSD.mini"),
        ],
    )

    captured = {}

    def _rates(symbol, tf, start, count):
        captured["symbol"] = symbol
        return RATES

    fake = sys.modules["MetaTrader5"]
    fake.copy_rates_from_pos = _rates

    data = await _provider().get_market_data(
        symbol="EURUSD", timeframe="FiveMinutes"
    )

    # Shortest suffix wins and is selected in the terminal.
    assert captured["symbol"] == "EURUSD.m"
    assert "EURUSD.m" in calls["select"]
    # HTTP contract: requested symbol echoed back, not the broker's.
    assert data.symbol == "EURUSD"


async def test_unknown_symbol_raises_with_retcode(fake_mt5):
    fake = sys.modules["MetaTrader5"]
    fake.symbol_info = lambda s: None
    fake.symbols_get = lambda p: []

    with pytest.raises(MT5DataError, match="10004"):
        await _provider().get_market_data(
            symbol="EURUSD", timeframe="FiveMinutes"
        )


async def test_unknown_timeframe_raises_value_error(fake_mt5):
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        await _provider().get_market_data(
            symbol="EURUSD", timeframe="TwoHours"
        )


async def test_copy_rates_none_raises_with_retcode(fake_mt5):
    fake = sys.modules["MetaTrader5"]
    fake.copy_rates_from_pos = lambda *a: None

    with pytest.raises(MT5DataError, match="10004"):
        await _provider().get_market_data(
            symbol="EURUSD", timeframe="FiveMinutes"
        )


async def test_malformed_row_is_skipped_not_fatal(fake_mt5):
    bad = dict(RATES[1], high=1.1000)  # high < close: inconsistent OHLC
    fake = sys.modules["MetaTrader5"]
    fake.copy_rates_from_pos = lambda *a: [
        RATES[0], bad, RATES[2],
    ]

    data = await _provider().get_market_data(
        symbol="EURUSD", timeframe="FiveMinutes"
    )

    assert len(data.candles) == 2


async def test_duplicate_rows_are_deduplicated(fake_mt5):
    fake = sys.modules["MetaTrader5"]
    fake.copy_rates_from_pos = lambda *a: RATES + [RATES[2]]

    data = await _provider().get_market_data(
        symbol="EURUSD", timeframe="FiveMinutes"
    )

    assert len(data.candles) == 3


async def test_connection_failure_becomes_data_error(monkeypatch):
    _install(monkeypatch)

    def _boom(**kwargs):
        raise MT5ConnectionError("terminal down")

    monkeypatch.setattr(mod, "connect", _boom)

    with pytest.raises(MT5DataError, match="connection failed"):
        await _provider().get_market_data(
            symbol="EURUSD", timeframe="FiveMinutes"
        )


# -- tick & depth extras ---------------------------------------------------


def test_get_tick_success(fake_mt5):
    tick = _provider().get_tick("EURUSD")

    assert tick.bid == 1.1033
    assert tick.ask == 1.1035
    assert tick.time.tzinfo is not None


def test_get_tick_none_raises_with_retcode(fake_mt5):
    fake = sys.modules["MetaTrader5"]
    fake.symbol_info_tick = lambda s: None

    with pytest.raises(MT5DataError, match="10004"):
        _provider().get_tick("EURUSD")


def test_get_depth_splits_bids_and_asks(fake_mt5):
    depth = _provider().get_depth("EURUSD")

    assert depth.bids == [(1.1010, 10.0)]
    assert depth.asks == [(1.1008, 7.0)]


def test_get_depth_retries_after_book_add(fake_mt5):
    fake, calls = fake_mt5
    fake.market_book_get = lambda s: None  # never succeeds

    with pytest.raises(MT5DataError, match="10004"):
        _provider().get_depth("EURUSD")

    # First None triggered exactly one market_book_add retry.
    assert calls["book_add"] == 1


# -- factory wiring --------------------------------------------------------


def test_factory_mt5_missing_credentials_raises(monkeypatch):
    from app.services.market_data_provider_factory import (
        create_market_data_provider,
    )

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mt5")

    for var in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError, match="MT5_LOGIN"):
        create_market_data_provider()


def test_factory_mt5_returns_provider_lazily(monkeypatch):
    from app.services.market_data_provider_factory import (
        create_market_data_provider,
    )

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setenv("MT5_LOGIN", "12345")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "Demo-Server")
    monkeypatch.delitem(sys.modules, "MetaTrader5", raising=False)

    provider = create_market_data_provider()

    assert isinstance(provider, MT5MarketDataProvider)
    # Construction never touches the terminal or imports the package.
    assert "MetaTrader5" not in sys.modules


def test_factory_unknown_provider_raises(monkeypatch):
    from app.services.market_data_provider_factory import (
        create_market_data_provider,
    )

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "bybit")

    with pytest.raises(RuntimeError, match="Unknown MARKET_DATA_PROVIDER"):
        create_market_data_provider()


def test_factory_twelve_missing_key_raises(monkeypatch):
    from app.services.market_data_provider_factory import (
        create_market_data_provider,
    )

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "twelve")
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TWELVE_DATA_API_KEY"):
        create_market_data_provider()


def test_missing_configuration_switches_with_provider(monkeypatch):
    from app.config import missing_configuration

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mt5")

    for var in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
        monkeypatch.delenv(var, raising=False)

    missing = missing_configuration()

    assert "MT5_LOGIN" in missing
    assert "MT5_SERVER" in missing
    # Twelve Data's key is irrelevant on the mt5 channel.
    assert "TWELVE_DATA_API_KEY" not in missing
