import asyncio
import os

from dotenv import load_dotenv

from app.data.downloader import HistoricalDataDownloader


load_dotenv()


async def main():
    api_key = os.getenv("TWELVE_DATA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not configured."
        )

    downloader = HistoricalDataDownloader(api_key)

    df = await downloader.download(
        symbol="EUR/USD",
        interval="15min",
        output_file="data/historical/EURUSD_15m.csv",
        start_date="2025-01-01",
        end_date="2026-01-01",
    )

    print(f"Rows downloaded: {len(df)}")
    print()
    print(df.head())
    print()
    print(df.tail())


if __name__ == "__main__":
    asyncio.run(main())