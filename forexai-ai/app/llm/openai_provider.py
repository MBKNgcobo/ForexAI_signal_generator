import asyncio
import logging
import random
import time

from openai import AsyncOpenAI

from app.llm.llm_errors import LLMUnavailableError
from app.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    import os

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


class OpenAIProvider(LLMProvider):
    """OpenAI-backed provider with OpenRouter-style retry discipline.

    Phase 2 (SQA): previously a single unguarded ``responses.create`` — any
    429/5xx/timeout/empty output propagated as a raw exception (500 at the
    API layer). Now retries transient failures with exponential backoff +
    deadline and maps exhaustion to ``LLMUnavailableError`` (503), exactly
    like the OpenRouter path, so both providers share one error contract.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        client=None,
    ):
        if not api_key:
            raise ValueError("OpenAI API key is required.")

        if not model:
            raise ValueError("OpenAI model is required.")

        self.client = client or AsyncOpenAI(api_key=api_key)

        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        max_attempts = 3
        base_delay = _env_float("OPENAI_RETRY_BASE_SECONDS", 1.5)
        max_delay = max(base_delay, _env_float("OPENAI_RETRY_MAX_SECONDS", 8.0))
        deadline = _env_float("OPENAI_REQUEST_DEADLINE_SECONDS", 60.0)

        started_at = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.client.responses.create(
                    model=self.model,
                    instructions=system_prompt,
                    input=user_prompt,
                )

                text = getattr(response, "output_text", "")

                if not text or not str(text).strip():
                    raise ValueError("OpenAI returned an empty completion.")

                return str(text)

            except LLMUnavailableError:
                raise

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "OpenAI attempt %d/%d failed: %s: %s",
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    exc,
                )

                if attempt >= max_attempts:
                    break

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                delay += random.uniform(0.0, 0.5)

                if time.monotonic() - started_at + delay >= deadline:
                    break

                await asyncio.sleep(delay)

        raise LLMUnavailableError(
            f"OpenAI could not complete the request after {max_attempts} "
            f"attempt(s): {last_error}"
        ) from last_error
    