from openai import AsyncOpenAI

from app.llm.llm_provider import LLMProvider


class OpenAIProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        model: str,
    ):
        self.client = AsyncOpenAI(
            api_key=api_key
        )

        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = await self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
        )

        return response.output_text
    