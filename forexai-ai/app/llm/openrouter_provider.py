import asyncio
import logging
import os
import random
import time
from collections.abc import Sequence

import openai
from openai import AsyncOpenAI

from app.llm.llm_errors import LLMUnavailableError
from app.llm.llm_provider import LLMProvider
from app.observability.metrics import record_llm_failure, record_llm_request

logger = logging.getLogger(__name__)


class _RetryableResponseError(RuntimeError):
    """The provider answered but with unusable content.

    A retry (possibly on another model) is worthwhile, unlike a bad request.
    """


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return default

    try:
        return int(raw)

    except ValueError:
        logger.warning(
            "Invalid %s=%r, using %d",
            name,
            raw,
            default,
        )
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return default

    try:
        return float(raw)

    except ValueError:
        logger.warning(
            "Invalid %s=%r, using %s",
            name,
            raw,
            default,
        )
        return default


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)

    if isinstance(status, int):
        return status

    response = getattr(exc, "response", None)

    status = getattr(response, "status_code", None)

    return status if isinstance(status, int) else None


def _is_retryable(exc: Exception) -> bool:
    """Rate limits, server errors and connection drops deserve a retry."""

    if isinstance(exc, _RetryableResponseError):
        return True

    if isinstance(
        exc,
        (
            openai.APIConnectionError,
            openai.APITimeoutError,
        ),
    ):
        return True

    status = _status_code(exc)

    if status is None:
        return False

    return status in {408, 429} or status >= 500


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    if headers is None:
        return None

    try:
        raw = headers.get("retry-after")

    except Exception:
        return None

    if raw is None:
        return None

    try:
        return max(0.0, float(raw))

    except (TypeError, ValueError):
        return None



class OpenRouterProvider(LLMProvider):
    """
    OpenRouter-backed LLM provider.

    The OpenAI SDK is used only as the HTTP client.
    Requests are sent to OpenRouter's OpenAI-compatible API.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_models: Sequence[str] | None = None,
        site_url: str | None = None,
        site_name: str | None = None,
    ) -> None:

        if not api_key:
            raise ValueError(
                "OpenRouter API key is required."
            )

        if not model:
            raise ValueError(
                "OpenRouter primary model is required."
            )

        fallbacks = list(
            fallback_models or []
        )

        if len(fallbacks) > 3:
            raise ValueError(
                "OpenRouter supports a maximum of 3 fallback models."
            )

        headers: dict[str, str] = {}

        if site_url:
            headers["HTTP-Referer"] = site_url

        if site_name:
            headers["X-OpenRouter-Title"] = site_name

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers=headers or None,
        )

        self.model = model
        self.fallback_models = fallbacks

    def _candidate_models(self) -> list[str]:
        """Primary model first, then the fallbacks, without duplicates."""

        candidates: list[str] = []

        for model in [self.model, *self.fallback_models]:

            if model and model not in candidates:
                candidates.append(model)

        return candidates

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Ask OpenRouter, retrying transient failures across models.

        Free OpenRouter models are served from shared pools that throttle
        with 429s, so a single attempt is not enough. Every model is retried
        with exponential backoff (honouring Retry-After) before moving on to
        the next one, and a deadline stops a congested run from hanging.
        """

        candidates = self._candidate_models()

        max_attempts = max(
            1,
            _env_int("OPENROUTER_MAX_ATTEMPTS", 3),
        )

        base_delay = max(
            0.0,
            _env_float("OPENROUTER_RETRY_BASE_SECONDS", 1.5),
        )

        max_delay = max(
            base_delay,
            _env_float("OPENROUTER_RETRY_MAX_SECONDS", 8.0),
        )

        deadline = max(
            0.0,
            _env_float("OPENROUTER_REQUEST_DEADLINE_SECONDS", 60.0),
        )

        started_at = time.monotonic()

        failures: list[str] = []

        last_error: Exception | None = None

        for model in candidates:

            for attempt in range(1, max_attempts + 1):

                if time.monotonic() - started_at >= deadline:

                    failures.append(f"{model}: deadline exceeded")

                    logger.warning(
                        "OpenRouter deadline of %.1fs reached; giving up.",
                        deadline,
                    )

                    break

                try:

                    result = await self._request(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    )

                    record_llm_request("openrouter", success=True)

                    return result

                except Exception as exc:

                    last_error = exc

                    record_llm_failure("openrouter", str(exc))

                    if not _is_retryable(exc):

                        logger.warning(
                            "OpenRouter error for %s is not retryable; "
                            "moving to the next model.",
                            model,
                        )

                        break

                    failures.append(
                        f"{model}: {type(exc).__name__}"
                    )

                    if attempt == max_attempts:
                        break

                    delay = min(
                        base_delay * (2 ** (attempt - 1)),
                        max_delay,
                    )

                    retry_after = _retry_after_seconds(exc)

                    if retry_after is not None:
                        delay = max(
                            delay,
                            min(retry_after, max_delay),
                        )

                    delay += random.uniform(0.0, 0.5)

                    remaining = deadline - (
                        time.monotonic() - started_at
                    )

                    if remaining <= 0:
                        break

                    await asyncio.sleep(
                        min(delay, remaining)
                    )

        raise LLMUnavailableError(
            "OpenRouter could not complete the request after "
            f"{len(failures)} attempt(s): "
            + "; ".join(failures)
        ) from last_error

    async def _request(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Perform a single OpenRouter call and validate the completion."""

        response = (
            await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0,
            )
        )

        if response is None:
            raise _RetryableResponseError(
                "OpenRouter returned no response."
            )

        choices = getattr(
            response,
            "choices",
            None,
        )

        if not choices:
            raw_response = None

            try:
                raw_response = response.model_dump()
            except Exception:
                raw_response = repr(response)

            raise _RetryableResponseError(
                "OpenRouter returned no completion choices. "
                f"Response: {raw_response}"
            )

        message = getattr(
            choices[0],
            "message",
            None,
        )

        if message is None:
            raise _RetryableResponseError(
                "OpenRouter returned a completion without a message."
            )

        content = getattr(
            message,
            "content",
            None,
        )

        if not content or not str(content).strip():
            raise _RetryableResponseError(
                "OpenRouter returned an empty completion."
            )

        return str(content)