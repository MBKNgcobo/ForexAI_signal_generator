from datetime import date
from typing import Any

import httpx


class SOTWClient:
    def __init__(
        self,
        base_url: str = (
            "https://statisticsoftheworld.com"
        ),
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = httpx.Timeout(
            timeout_seconds
        )

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}

        return {
            "X-API-Key": self.api_key
        }

    async def get_history(
        self,
        indicator: str,
        country: str,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/api/v1/"
            f"history/{indicator}/{country}"
        )

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.get(
                url,
                headers=self._headers(),
            )

        response.raise_for_status()

        return response.json()

    async def get_series(
        self,
        series_id: str,
        country: str,
        from_date: date | None = None,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/api/v1/"
            f"series/{series_id}"
        )

        params: dict[str, str] = {
            "geo": country,
        }

        if from_date:
            params["from"] = (
                from_date.isoformat()
            )

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._headers(),
            )

        response.raise_for_status()

        return response.json()