from app.llm.llm_provider import LLMProvider


class FakeLLMProvider(LLMProvider):

    def __init__(
        self,
        response: str,
    ):
        self.response = response

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return self.response