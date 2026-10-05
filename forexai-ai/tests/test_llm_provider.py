"""LLM contract + Phase 2 retry parity (OpenAI vs OpenRouter).

OpenAI previously made one unguarded call: any 429/5xx/timeout/empty output
escaped as a raw exception (500 at the API layer). It now retries with
backoff + deadline and maps exhaustion to LLMUnavailableError (503),
exactly like the OpenRouter path.
"""

import pytest

from app.llm.llm_errors import LLMUnavailableError
from app.llm.llm_provider import LLMProvider
from app.llm.openai_provider import OpenAIProvider


class FakeLLMProvider(LLMProvider):

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return "TEST RESPONSE"


@pytest.mark.asyncio
async def test_llm_provider_contract():

    provider = FakeLLMProvider()

    result = await provider.generate(
        system_prompt="You are a test model.",
        user_prompt="Hello.",
    )

    assert result == "TEST RESPONSE"


class _ScriptedResponses:
    """Fake ``client.responses`` honouring a script of outputs/errors."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        action = self.script[min(self.calls - 1, len(self.script) - 1)]

        if isinstance(action, Exception):
            raise action

        class _Response:
            output_text = action

        return _Response()


class _ScriptedClient:
    def __init__(self, script: list):
        self.responses = _ScriptedResponses(script)


@pytest.mark.asyncio
async def test_openai_retries_transient_then_returns():
    provider = OpenAIProvider(
        api_key="dummy",
        model="gpt-test",
        client=_ScriptedClient([RuntimeError("boom"), "  hello  "]),
    )

    result = await provider.generate(system_prompt="s", user_prompt="u")

    assert result == "  hello  "
    assert provider.client.responses.calls == 2


@pytest.mark.asyncio
async def test_openai_empty_output_is_retried_then_mapped_to_503(monkeypatch):
    monkeypatch.setenv("OPENAI_RETRY_BASE_SECONDS", "0.01")
    monkeypatch.setenv("OPENAI_RETRY_MAX_SECONDS", "0.02")
    monkeypatch.setenv("OPENAI_REQUEST_DEADLINE_SECONDS", "5")

    provider = OpenAIProvider(
        api_key="dummy",
        model="gpt-test",
        client=_ScriptedClient(["   ", " \t ", ""]),
    )

    with pytest.raises(LLMUnavailableError):
        await provider.generate(system_prompt="s", user_prompt="u")

    assert provider.client.responses.calls == 3


@pytest.mark.asyncio
async def test_openai_exhaustion_maps_to_llm_unavailable_not_raw_error(
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_RETRY_BASE_SECONDS", "0.01")
    monkeypatch.setenv("OPENAI_RETRY_MAX_SECONDS", "0.02")
    monkeypatch.setenv("OPENAI_REQUEST_DEADLINE_SECONDS", "5")

    provider = OpenAIProvider(
        api_key="dummy",
        model="gpt-test",
        client=_ScriptedClient([RuntimeError("down")]),
    )

    with pytest.raises(LLMUnavailableError, match="could not complete"):
        await provider.generate(system_prompt="s", user_prompt="u")