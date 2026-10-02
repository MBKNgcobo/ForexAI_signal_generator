"""HTTP boundary tests: validation, authentication and error mapping.

These assert that bad input and missing configuration surface as 4xx/5xx
responses with actionable details instead of unhandled 500s.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import expected_api_key
from app.main import app


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    """Run with the shared-secret guard off and no cached provider.

    Clearing the provider cache matters because a service built while
    ``TWELVE_DATA_API_KEY`` was set would otherwise leak into the test that
    asserts the missing-key 503.
    """

    from app.api.market_data import build_market_data_service

    monkeypatch.delenv("AI_SERVICE_API_KEY", raising=False)
    expected_api_key.cache_clear()
    build_market_data_service.cache_clear()
    yield
    expected_api_key.cache_clear()
    build_market_data_service.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def api_key_guard(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_API_KEY", "unit-test-secret")
    expected_api_key.cache_clear()
    return "unit-test-secret"


def test_health_is_public(client):

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == (
        "ForexAI AI Service is running"
    )


def test_unknown_timeframe_is_rejected(client):

    response = client.get(
        "/market-data/EURUSD",
        params={"timeframe": "TwoHours"},
    )

    assert response.status_code == 422


def test_malformed_symbol_is_rejected(client):

    response = client.get(
        "/market-data/EUR",
        params={"timeframe": "FifteenMinutes"},
    )

    assert response.status_code == 422


def test_out_of_range_limit_is_rejected(client):

    response = client.get(
        "/market-data/EURUSD",
        params={"limit": 0},
    )

    assert response.status_code == 422


def test_all_supported_timeframes_are_accepted_by_schema(client):

    for timeframe in (
        "OneMinute",
        "FiveMinutes",
        "FifteenMinutes",
        "OneHour",
        "FourHours",
        "OneDay",
    ):
        response = client.get(
            "/market-data/EURUSD",
            params={"timeframe": timeframe},
        )

        # 200/400/503 are all acceptable here - what must not happen is a
        # schema-level 422, because every advertised timeframe is valid.
        assert response.status_code != 422, timeframe


def test_market_data_service_is_reused_between_requests(monkeypatch):

    from app.api.market_data import build_market_data_service

    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-key")

    build_market_data_service.cache_clear()

    try:
        first = build_market_data_service()
        second = build_market_data_service()

        assert first is second

    finally:
        build_market_data_service.cache_clear()


def test_missing_market_data_key_returns_503(client, monkeypatch):

    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)

    response = client.get(
        "/market-data/EURUSD",
        params={"timeframe": "FifteenMinutes"},
    )

    assert response.status_code == 503
    assert "TWELVE_DATA_API_KEY" in response.json()["detail"]


def test_analysis_rejects_unknown_timeframe_before_running_graph(client):

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "1",
            "symbol": "EURUSD",
            "timeframe": "EightHours",
        },
    )

    assert response.status_code == 422


def test_analysis_rejects_malformed_symbol(client):

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "1",
            "symbol": "EU",
            "timeframe": "OneHour",
        },
    )

    assert response.status_code == 422


def test_analysis_returns_400_for_unsupported_pair(client):

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "1",
            "symbol": "ZZZUSD",
            "timeframe": "OneHour",
        },
    )

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_guard_is_disabled_without_configuration(client):

    response = client.get(
        "/market-data/EURUSD",
        params={"timeframe": "FifteenMinutes"},
    )

    # The guard is a no-op, so this fails on configuration, not auth.
    assert response.status_code != 401


def test_guard_rejects_missing_key(client, api_key_guard):

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "1",
            "symbol": "ZZZUSD",
            "timeframe": "OneHour",
        },
    )

    assert response.status_code == 401


def test_guard_rejects_wrong_key(client, api_key_guard):

    response = client.post(
        "/analysis",
        headers={"X-API-Key": "wrong"},
        json={
            "forex_pair_id": "1",
            "symbol": "ZZZUSD",
            "timeframe": "OneHour",
        },
    )

    assert response.status_code == 401


def test_guard_accepts_correct_key(client, api_key_guard):

    response = client.post(
        "/analysis",
        headers={"X-API-Key": api_key_guard},
        json={
            "forex_pair_id": "1",
            "symbol": "ZZZUSD",
            "timeframe": "OneHour",
        },
    )

    # Auth passed; the request then fails validation as expected.
    assert response.status_code == 400
