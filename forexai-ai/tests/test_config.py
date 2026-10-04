"""Configuration helpers.

Missing configuration must be reportable without crashing, and CORS parsing
must be exact (an empty value disables CORS entirely).
"""

from app.config import (
    cors_origins,
    ensemble_models,
    ensemble_weights,
    expected_api_key,
    get_env,
    llm_provider_name,
    missing_configuration,
)


def test_get_env_strips_and_defaults(monkeypatch):
    monkeypatch.setenv("SOME_VALUE", "  spaced  ")
    assert get_env("SOME_VALUE") == "spaced"

    monkeypatch.setenv("SOME_VALUE", "   ")
    assert get_env("SOME_VALUE", "fallback") == "fallback"


def test_missing_configuration_reports_market_and_llm_keys(monkeypatch):
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    missing = missing_configuration()

    assert "TWELVE_DATA_API_KEY" in missing
    assert "OPENROUTER_API_KEY" in missing


def test_missing_configuration_is_empty_when_all_present(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    assert missing_configuration() == []


def test_llm_provider_defaults_to_openrouter(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert llm_provider_name() == "openrouter"


def test_cors_origins_parses_comma_separated(monkeypatch):
    cors_origins.cache_clear()
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "http://a , http://b")

    try:
        assert cors_origins() == ["http://a", "http://b"]
    finally:
        cors_origins.cache_clear()


def test_cors_origins_empty_disables_cors(monkeypatch):
    cors_origins.cache_clear()
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "")

    try:
        assert cors_origins() == []
    finally:
        cors_origins.cache_clear()


def test_expected_api_key_none_when_unset(monkeypatch):
    expected_api_key.cache_clear()
    monkeypatch.delenv("AI_SERVICE_API_KEY", raising=False)

    try:
        assert expected_api_key() is None
    finally:
        expected_api_key.cache_clear()


def test_ensemble_defaults(monkeypatch):
    ensemble_models.cache_clear()
    ensemble_weights.cache_clear()

    monkeypatch.delenv("ENSEMBLE_MODELS", raising=False)
    monkeypatch.delenv("ENSEMBLE_WEIGHTS", raising=False)

    try:
        assert ensemble_models() == (
            "random_forest",
            "xgboost",
            "logistic_regression",
        )
        assert ensemble_weights() == {
            "random_forest": 0.4,
            "xgboost": 0.4,
            "logistic_regression": 0.2,
        }
    finally:
        ensemble_models.cache_clear()
        ensemble_weights.cache_clear()


def test_ensemble_overrides_and_ignores_unknown(monkeypatch):
    ensemble_models.cache_clear()
    ensemble_weights.cache_clear()

    monkeypatch.setenv("ENSEMBLE_MODELS", "xgboost, bogus, logistic_regression")
    monkeypatch.setenv("ENSEMBLE_WEIGHTS", "xgboost=0.7,logistic_regression=bad")

    try:
        assert ensemble_models() == ("xgboost", "logistic_regression")

        weights = ensemble_weights()

        assert weights["xgboost"] == 0.7
        # A malformed entry keeps the default rather than crashing.
        assert weights["logistic_regression"] == 0.2
    finally:
        ensemble_models.cache_clear()
        ensemble_weights.cache_clear()
