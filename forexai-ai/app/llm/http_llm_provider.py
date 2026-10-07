import asyncio
import logging
import random
import time

import httpx

from app.llm.llm_errors import LLMUnavailableError
from app.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


def _is_retryable_status(status: int | None) -> bool:
    if status is None:
        return True
    return status in {408, 429} or status >= 500


class HttpLLMProvider(LLMProvider):

    def __init__(
        self,
        endpoint: str,
        timeout: float = 30.0,
        max_attempts: int = 3,
    ):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

        started_at = time.monotonic()
        deadline = 60.0
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout
                ) as client:

                    response = await client.post(
                        self.endpoint,
                        json=payload,
                    )

                    response.raise_for_status()

                    data = response.json()

                text = data.get("text") if isinstance(data, dict) else None
                if not text or not str(text).strip():
                    raise ValueError(
                        "HTTP LLM returned an empty completion."
                    )
                return str(text)
            except LLMUnavailableError:
                raise
            except ValueError as exc:
                # Empty/malformed payload: transient once, then 502-worthy.
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                await asyncio.sleep(0.5 * attempt + random.uniform(0.0, 0.3))
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                logger.warning(
                    "HTTP LLM attempt %d/%d failed: %s: %s",
                    attempt,
                    self.max_attempts,
                    type(exc).__name__,
                    exc,
                )
                if attempt >= self.max_attempts:
                    break
                await asyncio.sleep(1.0 * attempt + random.uniform(0.0, 0.5))
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )
                logger.warning(
                    "HTTP LLM attempt %d/%d failed: HTTP %s: %s",
                    attempt,
                    self.max_attempts,
                    status,
                    exc,
                )
                if not _is_retryable_status(status):
                    break
                if attempt >= self.max_attempts:
                    break
                if time.monotonic() - started_at >= deadline:
                    break
                await asyncio.sleep(1.0 * attempt + random.uniform(0.0, 0.5))
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "HTTP LLM attempt %d/%d failed: %s: %s",
                    attempt,
                    self.max_attempts,
                    type(exc).__name__,
                    exc,
                )
                if attempt >= self.max_attempts:
                    break
                await asyncio.sleep(1.0 * attempt)

        # Malformed/empty output maps to ValueError -> 502 at the API layer;
        # transport exhaustion maps to LLMUnavailableError -> 503.
        if isinstance(last_error, ValueError):
            raise ValueError(str(last_error)) from last_error
        raise LLMUnavailableError(
            f"HTTP LLM could not complete the request after "
            f"{self.max_attempts} attempt(s): {last_error}"
        ) from last_error