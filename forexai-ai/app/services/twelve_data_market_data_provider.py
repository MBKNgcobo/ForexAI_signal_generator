import logging
from datetime import datetime, timezone

import httpx

from app.schemas.market import MarketData
from app.services.market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


class TwelveDataMarketDataProvider(MarketDataProvider):

    BASE_URL = "https://api.twelvedata.com/time_series"

    INTERVAL_MAP = {
        "OneMinute": "1min",
        "FiveMinutes": "5min",
        "FifteenMinutes": "15min",
        "OneHour": "1h",
        "FourHours": "4h",
        "OneDay": "1day",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:

        if not self.api_key:
            raise ValueError(
                "Twelve Data API key is not configured."
            )

        interval = self.INTERVAL_MAP.get(timeframe)

        if interval is None:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        provider_symbol = self._format_symbol(symbol)

        params = {
            "symbol": provider_symbol,
            "interval": interval,
            "outputsize": limit,
            "timezone": "UTC",
            "apikey": self.api_key,
        }

        logger.debug(
            "Twelve Data request: %s / %s / %d",
            provider_symbol,
            interval,
            limit,
        )

        timeout = httpx.Timeout(
            connect=10.0,
            read=20.0,
            write=10.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.get(
                self.BASE_URL,
                params=params,
            )

        logger.debug(
            "Twelve Data response status: %s",
            response.status_code,
        )

        if response.status_code == 429:
            raise RuntimeError(
                "Twelve Data rate limit reached. "
                "Please wait before requesting more market data."
            )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "ok":
            message = (
                payload.get("message")
                or "Unknown Twelve Data error."
            )

            raise RuntimeError(
                f"Twelve Data error: {message}"
            )

        values = payload.get("values")

        if not values:
            raise RuntimeError(
                "Twelve Data returned no candle values."
            )

        candles = []

        for item in reversed(values):

            candles.append(
                {
                    "timestamp": self._normalize_timestamp(
                        item["datetime"]
                    ),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(
                        item.get("volume", 0.0)
                    ),
                }
            )

        return MarketData(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )

    @staticmethod
    def _format_symbol(symbol: str) -> str:

        if len(symbol) == 6:
            return (
                f"{symbol[:3]}/{symbol[3:]}"
            )

        return symbol

    @staticmethod
    def _normalize_timestamp(
        value: str,
    ) -> str:
        """Normalise a Twelve Data timestamp to a UTC ISO-8601 string.

        Twelve Data returns ``YYYY-MM-DD HH:MM:SS`` for intraday intervals but
        date-only ``YYYY-MM-DD`` for ``1day`` (and can return the ISO ``T``
        separator). The previous hard-coded ``strptime`` format therefore
        broke the advertised OneDay timeframe with a ValueError.
        """

        raw = (value or "").strip()

        # Tolerate the ISO-8601 separator and any trailing 'Z'/offset.
        normalised = raw.replace("T", " ").rstrip("Zz")

        dt: datetime | None = None

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(normalised, fmt)
                break
            except ValueError:
                continue

        if dt is None:
            # Last resort: let fromisoformat handle offsets it understands.
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(
                    f"Unsupported timestamp format: {value}"
                ) from exc

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(timezone.utc).isoformat()