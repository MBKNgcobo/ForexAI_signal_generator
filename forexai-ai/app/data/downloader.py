from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

BASE_URL = "https://api.twelvedata.com/time_series"


class HistoricalDataDownloader:
    def __init__(self, api_key: str, client: Optional[httpx.AsyncClient] = None):
        if not api_key:
            raise ValueError("Twelve Data API key is required.")
        self.api_key = api_key
        # Reuse external client or fall back to internal instance
        self._external_client = client

    async def download(
        self,
        symbol: str,
        interval: str,
        output_file: str,
        start_date: str,
        end_date: str,
        timeout_seconds: float = 30.0,
    ) -> pd.DataFrame:

        params = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "apikey": self.api_key,
            "format": "JSON",
            "outputsize": 5000,
        }

        # Use shared client if provided, otherwise create a single-use client
        client = self._external_client or httpx.AsyncClient(timeout=timeout_seconds)
        
        try:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as err:
            raise TimeoutError(f"TwelveData API request timed out for {symbol}: {err}") from err
        except httpx.HTTPStatusError as err:
            raise RuntimeError(f"TwelveData API HTTP error {err.response.status_code}: {err}") from err
        finally:
            if not self._external_client:
                await client.aclose()

        if data.get("status") == "error":
            raise RuntimeError(
                data.get("message", "Twelve Data request failed.")
            )

        values = data.get("values")
        if not values or not isinstance(values, list):
            raise RuntimeError(
                f"No valid historical market data returned for {symbol}."
            )

        df = pd.DataFrame(values)

        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        numeric_columns = ["open", "high", "low", "close"]
        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = 0.0

        df = df.sort_values("datetime").drop_duplicates(subset="datetime").reset_index(drop=True)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        return df