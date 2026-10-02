import pytest

from app.llm.llm_provider import LLMProvider


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