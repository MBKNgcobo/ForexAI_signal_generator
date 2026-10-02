from app.llm.llm_provider import LLMProvider


class DemoLLMProvider(LLMProvider):

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        return """
        {
            "direction": "BUY",
            "confidence": 0.80,
            "summary": "Demo LLM interpretation of bullish technical conditions.",
            "reasoning": [
                "EMA20 is above EMA50.",
                "The technical evidence indicates positive momentum."
            ]
        }
        """