"""Observability: request IDs, structured logs, Prometheus metrics."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import (
    JsonFormatter,
    formatter_for,
    get_request_id,
    set_request_id,
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_version_reports_service_metadata(client):
    response = client.get("/version")

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "ForexAI AI Service"
    assert body["version"]


def test_metrics_endpoint_exposes_request_counter(client):
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "forexai_http_requests_total" in response.text


def test_request_id_is_echoed_when_supplied(client):
    response = client.get(
        "/health",
        headers={"X-Request-ID": "trace-123"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-123"


def test_request_id_is_generated_when_absent(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("x-request-id")


def test_json_formatter_renders_request_id_as_parseable_json():
    import logging

    set_request_id("req-abc")

    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )

        payload = json.loads(JsonFormatter().format(record))

        assert payload["message"] == "hello"
        assert payload["level"] == "INFO"
        assert payload["request_id"] == "req-abc"

    finally:
        set_request_id("")


def test_formatter_for_selects_json_or_text():
    assert isinstance(formatter_for("json"), JsonFormatter)
    assert isinstance(
        formatter_for("text"),
        JsonFormatter,
    ) is False
    assert get_request_id() == "" or isinstance(get_request_id(), str)
