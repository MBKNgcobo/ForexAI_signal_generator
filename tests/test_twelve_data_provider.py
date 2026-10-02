"""Provider boundary tests: every advertised timeframe must survive parsing."""

import pytest

from app.schemas.market import Timeframe
from app.services.twelve_data_market_data_provider import (
    TwelveDataMarketDataProvider,
)


def _normalize(value: str) -> str:
    return TwelveDataMarketDataProvider._normalize_timestamp(value)


def test_intraday_timestamp_is_normalised_to_utc_iso():

    assert _normalize("2026-03-01 14:30:00") == "2026-03-01T14:30:00+00:00"


def test_date_only_timestamp_for_daily_bars():

    # Twelve Data returns bare dates for the 1day interval. The previous
    # implementation raised ValueError, which broke the OneDay timeframe.
    assert _normalize("2026-03-01") == "2026-03-01T00:00:00+00:00"


def test_iso_separator_is_accepted():

    assert _normalize("2026-03-01T14:30:00") == "2026-03-01T14:30:00+00:00"


def test_explicit_offset_is_preserved_and_converted_to_utc():

    assert _normalize("2026-03-01T16:30:00+02:00") == (
        "2026-03-01T14:30:00+00:00"
    )


def test_minute_precision_is_accepted():

    assert _normalize("2026-03-01 14:30") == "2026-03-01T14:30:00+00:00"


def test_garbage_timestamp_is_rejected_with_value_error():

    with pytest.raises(ValueError, match="Unsupported timestamp format"):
        _normalize("not-a-timestamp")


@pytest.mark.parametrize(
    ("timeframe", "interval"),
    list(TwelveDataMarketDataProvider.INTERVAL_MAP.items()),
)
def test_every_schema_timeframe_maps_to_a_provider_interval(
    timeframe,
    interval,
):
    assert timeframe in {item.value for item in Timeframe}
    assert TwelveDataMarketDataProvider.INTERVAL_MAP[timeframe] == interval


def test_unknown_timeframe_raises_value_error():

    provider = TwelveDataMarketDataProvider(api_key="dummy")

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        # The key check happens first, so a configured key is required to
        # reach the interval lookup.
        import asyncio

        asyncio.run(
            provider.get_market_data(
                symbol="EURUSD",
                timeframe="TwoHours",
            )
        )
