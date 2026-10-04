"""Health and readiness probes.

``/health`` is liveness (always 200) and ``/ready`` is readiness (depends on
configuration). Keeping them distinct lets an orchestrator route traffic while
the service is up but not yet fully configured.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_is_public_and_reports_metadata(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ForexAI AI Service is running"
    assert body["service"] == "ForexAI AI Service"
    assert body["version"]


def test_ready_returns_503_when_configuration_missing(client, monkeypatch):
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.headers.get("retry-after") == "30"


def test_ready_returns_200_when_configured(client, monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
