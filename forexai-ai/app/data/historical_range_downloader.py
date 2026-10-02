import asyncio
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd


BASE_URL = "https://api.twelvedata.com/time_series"


class HistoricalRangeDownloader:

    def __init__(
        self,
        api_key: str,
        chunk_days: int = 40,
        request_delay_seconds: float = 65.0,
        max_retries: int = 5,
        chunk_directory: str = (
            "data/historical/chunks"
        ),
    ):
        self.api_key = api_key
        self.chunk_days = chunk_days
        self.request_delay_seconds = (
            request_delay_seconds
        )
        self.max_retries = max_retries
        self.chunk_directory = Path(
            chunk_directory
        )

    async def _download_chunk(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
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

        for attempt in range(
            1,
            self.max_retries + 1,
        ):

            try:

                print(
                    f"Request attempt "
                    f"{attempt}/"
                    f"{self.max_retries}"
                )

                response = await client.get(
                    BASE_URL,
                    params=params,
                )

                # -------------------------------------------------
                # Rate limiting
                # -------------------------------------------------

                if response.status_code == 429:

                    if attempt >= self.max_retries:

                        raise RuntimeError(
                            "Twelve Data rate limit "
                            "persisted after maximum retries."
                        )

                    wait_seconds = 65

                    print(
                        "429 Too Many Requests."
                    )

                    print(
                        f"Waiting {wait_seconds} "
                        f"seconds before retry..."
                    )

                    await asyncio.sleep(
                        wait_seconds
                    )

                    continue

                # -------------------------------------------------
                # Other HTTP errors
                # -------------------------------------------------

                response.raise_for_status()

                data = response.json()

                # -------------------------------------------------
                # Twelve Data application-level error
                # -------------------------------------------------

                if data.get("status") == "error":

                    message = data.get(
                        "message",
                        "Unknown Twelve Data error."
                    )

                    raise RuntimeError(
                        f"Twelve Data error "
                        f"for {start_date} -> "
                        f"{end_date}: {message}"
                    )

                values = data.get("values")

                if not values:

                    print(
                        "No data returned for "
                        f"{start_date} -> {end_date}"
                    )

                    return pd.DataFrame()

                # -------------------------------------------------
                # Convert response to DataFrame
                # -------------------------------------------------

                df = pd.DataFrame(values)

                # -------------------------------------------------
                # Datetime
                # -------------------------------------------------

                df["datetime"] = pd.to_datetime(
                    df["datetime"],
                    utc=True,
                )

                # -------------------------------------------------
                # Numeric fields
                # -------------------------------------------------

                numeric_columns = [
                    "open",
                    "high",
                    "low",
                    "close",
                ]

                for column in numeric_columns:

                    if column in df.columns:

                        df[column] = pd.to_numeric(
                            df[column],
                            errors="coerce",
                        )

                # -------------------------------------------------
                # Volume
                #
                # Spot FX often has no real exchange volume.
                # We therefore preserve volume when supplied,
                # otherwise use zero.
                # -------------------------------------------------

                if "volume" in df.columns:

                    df["volume"] = pd.to_numeric(
                        df["volume"],
                        errors="coerce",
                    )

                else:

                    df["volume"] = 0.0

                # -------------------------------------------------
                # Basic validation
                # -------------------------------------------------

                required_columns = [
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]

                missing_columns = [
                    column
                    for column in required_columns
                    if column not in df.columns
                ]

                if missing_columns:

                    raise RuntimeError(
                        "Historical response is missing "
                        f"columns: {missing_columns}"
                    )

                # -------------------------------------------------
                # Remove invalid rows
                # -------------------------------------------------

                df = df.dropna(
                    subset=[
                        "datetime",
                        "open",
                        "high",
                        "low",
                        "close",
                    ]
                )

                # -------------------------------------------------
                # Remove duplicate timestamps
                # -------------------------------------------------

                df = (
                    df.drop_duplicates(
                        subset="datetime"
                    )
                    .sort_values("datetime")
                    .reset_index(drop=True)
                )

                return df

            except httpx.RequestError as exc:

                if attempt >= self.max_retries:
                    raise RuntimeError(
                        "Network request failed after "
                        "maximum retries."
                    ) from exc

                wait_seconds = (
                    self.request_delay_seconds
                    * attempt
                )

                print(
                    f"Network error: {exc}"
                )

                print(
                    f"Retrying in "
                    f"{wait_seconds:.0f} seconds..."
                )

                await asyncio.sleep(
                    wait_seconds
                )

        raise RuntimeError(
            "Historical data request failed."
        )

    def _get_chunk_file(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> Path:

        safe_symbol = (
            symbol
            .replace("/", "")
            .replace("\\", "")
        )

        filename = (
            f"{safe_symbol}_"
            f"{interval}_"
            f"{start_date}_"
            f"{end_date}.csv"
        )

        return (
            self.chunk_directory
            / filename
        )

    async def download_range(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        output_file: str,
    ) -> pd.DataFrame:

        start = date.fromisoformat(
            start_date
        )

        end = date.fromisoformat(
            end_date
        )

        if start >= end:

            raise ValueError(
                "start_date must be before end_date."
            )

        # ---------------------------------------------------------
        # Prepare chunk directory
        # ---------------------------------------------------------

        self.chunk_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        chunks: list[pd.DataFrame] = []

        current_start = start

        total_days = (
            end - start
        ).days

        estimated_chunks = (
            total_days
            + self.chunk_days
            - 1
        ) // self.chunk_days

        print(
            f"Downloading {symbol} {interval}"
        )

        print(
            f"Date range: "
            f"{start} -> {end}"
        )

        print(
            f"Chunk size: "
            f"{self.chunk_days} days"
        )

        print(
            f"Estimated requests: "
            f"{estimated_chunks}"
        )

        print(
            f"Chunk directory: "
            f"{self.chunk_directory}"
        )

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            chunk_number = 1

            while current_start < end:

                # -------------------------------------------------
                # Determine this chunk's date range
                # -------------------------------------------------

                current_end = min(
                    current_start
                    + timedelta(
                        days=self.chunk_days - 1
                    ),
                    end,
                )

                chunk_start_str = (
                    current_start.isoformat()
                )

                chunk_end_str = (
                    current_end.isoformat()
                )

                print()
                print(
                    "=" * 60
                )

                print(
                    f"Chunk "
                    f"{chunk_number}/"
                    f"{estimated_chunks}: "
                    f"{chunk_start_str} -> "
                    f"{chunk_end_str}"
                )

                # -------------------------------------------------
                # Determine chunk file path
                # -------------------------------------------------

                chunk_file = (
                    self._get_chunk_file(
                        symbol=symbol,
                        interval=interval,
                        start_date=chunk_start_str,
                        end_date=chunk_end_str,
                    )
                )

                # -------------------------------------------------
                # RESUME LOGIC
                #
                # If the chunk already exists, don't download it
                # again.
                # -------------------------------------------------

                if chunk_file.exists():

                    print(
                        "Chunk already exists."
                    )

                    print(
                        f"Loading: {chunk_file}"
                    )

                    try:

                        df = pd.read_csv(
                            chunk_file
                        )

                        df["datetime"] = (
                            pd.to_datetime(
                                df["datetime"],
                                utc=True,
                            )
                        )

                        print(
                            f"Loaded "
                            f"{len(df)} candles "
                            "from saved chunk."
                        )

                        chunks.append(df)

                    except Exception as exc:

                        print(
                            "Existing chunk could "
                            "not be loaded."
                        )

                        print(
                            f"Reason: {exc}"
                        )

                        print(
                            "Deleting corrupted "
                            "chunk and re-downloading."
                        )

                        chunk_file.unlink(
                            missing_ok=True
                        )

                        df = (
                            await self._download_chunk(
                                client=client,
                                symbol=symbol,
                                interval=interval,
                                start_date=chunk_start_str,
                                end_date=chunk_end_str,
                            )
                        )

                        if not df.empty:

                            df.to_csv(
                                chunk_file,
                                index=False,
                            )

                            print(
                                f"Saved chunk: "
                                f"{chunk_file}"
                            )

                            chunks.append(df)

                else:

                    # -------------------------------------------------
                    # Download chunk
                    # -------------------------------------------------

                    df = await self._download_chunk(
                        client=client,
                        symbol=symbol,
                        interval=interval,
                        start_date=chunk_start_str,
                        end_date=chunk_end_str,
                    )

                    if not df.empty:

                        print(
                            f"Received "
                            f"{len(df)} candles"
                        )

                        # -------------------------------------------------
                        # SAVE IMMEDIATELY
                        # -------------------------------------------------

                        df.to_csv(
                            chunk_file,
                            index=False,
                        )

                        print(
                            f"Saved chunk: "
                            f"{chunk_file}"
                        )

                        chunks.append(df)

                    else:

                        print(
                            "Received 0 candles."
                        )

                # -------------------------------------------------
                # Move to next chunk
                # -------------------------------------------------

                current_start = (
                    current_end
                    + timedelta(days=1)
                )

                chunk_number += 1

                # -------------------------------------------------
                # Wait before the next API request.
                #
                # Only wait if the next chunk is not already
                # available locally.
                # -------------------------------------------------

                if current_start < end:

                    next_chunk_end = min(
                        current_start
                        + timedelta(
                            days=self.chunk_days - 1
                        ),
                        end,
                    )

                    next_chunk_file = (
                        self._get_chunk_file(
                            symbol=symbol,
                            interval=interval,
                            start_date=current_start.isoformat(),
                            end_date=next_chunk_end.isoformat(),
                        )
                    )

                    if not next_chunk_file.exists():

                        print(
                            f"\nWaiting "
                            f"{self.request_delay_seconds:.0f} "
                            f"seconds before next API request..."
                        )

                        await asyncio.sleep(
                            self.request_delay_seconds
                        )

        # ---------------------------------------------------------
        # Make sure something was collected
        # ---------------------------------------------------------

        if not chunks:

            raise RuntimeError(
                "No historical data was downloaded."
            )

        print()
        print(
            "=" * 60
        )

        print(
            "Combining chunks..."
        )

        combined = pd.concat(
            chunks,
            ignore_index=True,
        )

        print(
            f"Rows before cleanup: "
            f"{len(combined)}"
        )

        # ---------------------------------------------------------
        # Final cleanup
        # ---------------------------------------------------------

        combined["datetime"] = pd.to_datetime(
            combined["datetime"],
            utc=True,
        )

        combined = (
            combined
            .drop_duplicates(
                subset="datetime"
            )
            .sort_values("datetime")
            .reset_index(drop=True)
        )

        print(
            f"Rows after cleanup: "
            f"{len(combined)}"
        )

        # ---------------------------------------------------------
        # Save complete historical dataset
        # ---------------------------------------------------------

        output_path = Path(
            output_file
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        combined.to_csv(
            output_path,
            index=False,
        )

        print(
            f"Saved complete dataset: "
            f"{output_path}"
        )

        return combined