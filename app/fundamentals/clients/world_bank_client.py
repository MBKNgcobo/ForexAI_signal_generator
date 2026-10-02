from typing import Any

import httpx


class WorldBankClient:
    def __init__(
        self,
        base_url: str = (
            "https://api.worldbank.org/v2"
        ),
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(
            timeout_seconds
        )

    async def get_indicator(
        self,
        country: str,
        indicator: str,
        start_year: int = 2018,
        end_year: int = 2026,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/country/"
            f"{country}/indicator/{indicator}"
        )

        params = {
            "format": "json",
            "per_page": "100",
            "date": (
                f"{start_year}:{end_year}"
            ),
        }

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            response = await client.get(
                url,
                params=params,
            )

        response.raise_for_status()

        payload = response.json()

        if (
            not isinstance(payload, list)
            or len(payload) < 2
        ):
            raise ValueError(
                "Unexpected World Bank response."
            )

        return {
            "metadata": payload[0],
            "data": payload[1] or [],
        }