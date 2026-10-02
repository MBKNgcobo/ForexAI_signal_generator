import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from app.data.historical_range_downloader import (
    HistoricalRangeDownloader,
)


# Project root:
# forexai-ai/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

async def main():

    api_key = os.getenv(
        "TWELVE_DATA_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not configured."
        )

    downloader = HistoricalRangeDownloader(
        api_key=api_key,
        chunk_days=40,
        request_delay_seconds=65.0,
    )

    df = await downloader.download_range(
        symbol="EUR/USD",
        interval="15min",
        start_date="2024-01-01",
        end_date="2026-09-01",
        output_file=(
            "data/historical/"
            "EURUSD_15m_full.csv"
        ),
    )

    print(
        "\n========== FINAL DATASET =========="
    )

    print(
        f"Rows: {len(df)}"
    )

    print(
        f"Start: {df['datetime'].min()}"
    )

    print(
        f"End: {df['datetime'].max()}"
    )

    print("Project root:", PROJECT_ROOT)
    print("Env file:", ENV_FILE)
    print("Env exists:", ENV_FILE.exists())
    print(
    "API key loaded:",
    bool(os.getenv("TWELVE_DATA_API_KEY"))
)

if __name__ == "__main__":
    asyncio.run(main())