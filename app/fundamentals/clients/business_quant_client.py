from typing import Any, Optional
import httpx


class BusinessQuantClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://data.businessquant.com",
        timeout_seconds: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:

        if not api_key:
            raise ValueError("BUSINESS_QUANT_API_KEY is required.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self._external_client = client

    async def get_economic_data(
        self,
        codes: list[str],
        period: str = "5y",
    ) -> dict[str, Any]:

        if not codes:
            raise ValueError("At least one Business Quant code is required.")

        cleaned_codes = [
            code.strip()[2:] if code.strip().startswith("E:") else code.strip()
            for code in codes
            if code.strip()
        ]

        if not cleaned_codes:
            raise ValueError("No valid Business Quant codes were supplied.")

        if len(cleaned_codes) > 5:
            raise ValueError("Business Quant allows a maximum of 5 economic codes per request.")

        url = f"{self.base_url}/economic"
        params = {
            "code": ",".join(cleaned_codes),
            "period": period,
            "api_key": self.api_key,
        }

        client = self._external_client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            trust_env=False,
        )

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as err:
            raise TimeoutError(f"Business Quant API request timed out: {err}") from err
        except httpx.HTTPStatusError as err:
            raise RuntimeError(f"Business Quant HTTP error {err.response.status_code}: {err}") from err
        finally:
            if not self._external_client:
                await client.aclose()

        if not isinstance(payload, dict):
            raise ValueError("Unexpected Business Quant response structure.")

        if "metadata" not in payload or "data" not in payload:
            raise ValueError("Business Quant response missing 'metadata' or 'data'.")

        return payload