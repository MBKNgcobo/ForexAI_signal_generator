import os

from app.llm.http_llm_provider import HttpLLMProvider
from app.llm.llm_provider import LLMProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.openrouter_provider import OpenRouterProvider


def _get_fallback_models() -> list[str]:
    raw = os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "",
    )

    if not raw.strip():
        return []

    models = [
        model.strip()
        for model in raw.split(",")
        if model.strip()
    ]

    if len(models) > 3:
        raise RuntimeError(
            "OPENROUTER_FALLBACK_MODELS "
            "may contain at most 3 models."
        )

    return models


def create_llm_provider() -> LLMProvider:
    provider = os.getenv(
        "LLM_PROVIDER",
        "openrouter",
    ).strip().lower()

    if provider == "openrouter":
        api_key = os.getenv(
            "OPENROUTER_API_KEY"
        )

        model = os.getenv(
            "OPENROUTER_MODEL",
            "deepseek/deepseek-v4-flash-0731:free",
        )

        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not configured."
            )

        fallback_models = _get_fallback_models()

        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            fallback_models=fallback_models,
            site_url=os.getenv(
                "OPENROUTER_SITE_URL"
            ),
            site_name=os.getenv(
                "OPENROUTER_SITE_NAME",
                "ForexAI",
            ),
        )

    if provider == "openai":
        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        model = os.getenv(
            "OPENAI_MODEL"
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        if not model:
            raise RuntimeError(
                "OPENAI_MODEL is not configured."
            )

        return OpenAIProvider(
            api_key=api_key,
            model=model,
        )

    if provider == "http":
        endpoint = os.getenv(
            "LLM_ENDPOINT"
        )

        if not endpoint:
            raise RuntimeError(
                "LLM_ENDPOINT is not configured."
            )

        return HttpLLMProvider(
            endpoint=endpoint
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )