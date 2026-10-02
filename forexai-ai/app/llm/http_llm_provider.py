import httpx

from app.llm.llm_provider import LLMProvider


class HttpLLMProvider(LLMProvider):

    def __init__(
        self,
        endpoint: str,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint
        self.timeout = timeout

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.post(
                self.endpoint,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        return data["text"]