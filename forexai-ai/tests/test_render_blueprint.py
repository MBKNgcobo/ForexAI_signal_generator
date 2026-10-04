"""The Render blueprint is a deployment contract, so it gets tested too.

``render.yaml`` sits at the repository root and defines the whole hosted
stack. Two real defects shipped in an earlier revision of it:

* ``RAG_DB_PASSWORD`` had neither a ``value`` nor ``sync: false``, so the
  RAG store would have been left unconfigured on deploy;
* ``Cors__AllowedOrigins__0`` had drifted onto the migration *cron job*
  instead of the web API that serves browsers.

Both passed a naive "does the YAML parse and list four services" check,
because YAML happily accepts a mapping with a missing value and silently
keeps the last of two duplicate keys. These tests assert the semantics
instead: every variable resolves, no key is declared twice, no secret is
hardcoded, and the paths and probe endpoints actually exist.
"""

from pathlib import Path

import pytest
import yaml

#: forexai-ai/tests/ -> forexai-ai/ -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_PATH = REPO_ROOT / "render.yaml"

#: Values that must never be committed literally.
SECRET_TOKENS = ("PASSWORD", "KEY", "SECRET", "CONNECTION", "APIKEY")

EXPECTED_SERVICES = {
    "forexai-python-ai": "web",
    "forexai-csharp-api": "web",
    "forexai-dashboard": "web",
    "forexai-db-migrate": "cron",
}


@pytest.fixture(scope="module")
def blueprint() -> dict:
    return yaml.safe_load(BLUEPRINT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def services(blueprint: dict) -> dict:
    return {
        service["name"]: service
        for service in blueprint["services"]
    }


def _env(services: dict, name: str) -> dict:
    return {
        entry["key"]: entry
        for entry in services[name].get("envVars", [])
    }


def test_blueprint_exists_and_parses(blueprint):
    assert blueprint.get("services"), "render.yaml declares no services"


def test_declares_every_expected_service(services):
    assert set(services) == set(EXPECTED_SERVICES)


def test_service_types_match(services):
    for name, expected_type in EXPECTED_SERVICES.items():
        assert services[name]["type"] == expected_type, name


@pytest.mark.parametrize(
    "key",
    [
        "RAG_DB_HOST",
        "RAG_DB_PORT",
        "RAG_DB_NAME",
        "RAG_DB_USER",
        "RAG_DB_PASSWORD",
    ],
)
def test_rag_store_is_fully_configured(services, key):
    """The regression: a key with no value and no sync would 503 /analysis."""

    assert key in _env(services, "forexai-python-ai"), key


def test_every_env_var_resolves_to_exactly_one_source(services):
    """Render needs exactly one of value / generateValue / sync: false.

    Zero leaves the variable unset at runtime; more than one is ambiguous.
    """

    malformed = []

    for name, service in services.items():
        for entry in service.get("envVars", []):
            sources = sum(
                [
                    "value" in entry,
                    entry.get("sync") is False,
                    bool(entry.get("generateValue")),
                ]
            )

            if sources != 1:
                malformed.append((name, entry.get("key"), sources))

    assert not malformed, f"malformed env vars: {malformed}"


def test_no_env_var_is_declared_twice(services):
    """YAML keeps the last duplicate key silently; catch it here instead."""

    duplicates = []

    for name, service in services.items():
        keys = [entry["key"] for entry in service.get("envVars", [])]

        duplicates.extend(
            (name, key)
            for key in set(keys)
            if keys.count(key) > 1
        )

    assert not duplicates, f"duplicate env vars: {duplicates}"



def test_no_secret_is_hardcoded_in_the_blueprint(services):
    """Anything secret must be prompted for or generated, never committed."""

    offenders = []

    for name, service in services.items():
        for entry in service.get("envVars", []):
            key = entry.get("key", "").upper()

            if not any(token in key for token in SECRET_TOKENS):
                continue

            if "value" in entry:
                offenders.append((name, entry["key"]))

    assert not offenders, f"hardcoded secrets: {offenders}"


def test_cors_origin_is_on_the_web_api_not_the_cron_job(services):
    """The regression: CORS drifted onto the migration job.

    The browser-facing service is csharp-api. Putting the allowed origin on
    the cron job leaves the API with an empty origin list, which blocks any
    direct cross-origin call.
    """

    assert "Cors__AllowedOrigins__0" in _env(
        services,
        "forexai-csharp-api",
    )

    assert "Cors__AllowedOrigins__0" not in _env(
        services,
        "forexai-db-migrate",
    )


def test_python_service_readiness_probe_is_configured(services):
    """``/health`` is liveness only; ``/ready`` is what proves config."""

    assert (
        services["forexai-python-ai"]["healthCheckPath"] == "/ready"
    )


def test_dashboard_and_api_probe_the_root_health_endpoint(services):
    """These services only expose /health at the root."""

    for name in ("forexai-csharp-api", "forexai-dashboard"):
        assert services[name]["healthCheckPath"] == "/health", name


def test_webhook_allowlist_covers_the_ephemeral_tunnel(services):
    """A quick tunnel is a new random hostname on every restart.

    The allowlist must therefore be the wildcard form; an exact host would
    stop matching the moment cloudflared is restarted.
    """

    allowlist = _env(services, "forexai-python-ai")["WEBHOOK_ALLOWLIST"]

    assert allowlist["value"].startswith("."), (
        "expected a wildcard entry such as '.trycloudflare.com'"
    )
    assert "trycloudflare.com" in allowlist["value"]


def test_hosted_generator_does_not_try_to_use_mt5(services):
    """MetaTrader5 is Windows-only and cannot exist in a Linux container."""

    provider = _env(services, "forexai-python-ai")["MARKET_DATA_PROVIDER"]

    assert provider["value"] == "twelve"


def test_build_contexts_and_dockerfiles_exist(services):
    """A moved or renamed directory would only fail at deploy time."""

    for name, service in services.items():
        context = REPO_ROOT / service["dockerContext"].lstrip("./")

        assert context.is_dir(), f"{name}: missing context {context}"

        dockerfile = context / Path(
            service["dockerfilePath"]
        ).name

        assert dockerfile.is_file(), f"{name}: missing {dockerfile}"


def test_dashboard_upstream_points_at_the_api_service(services):
    """Same-origin /api proxying depends on this being the real hostname."""

    upstream = _env(services, "forexai-dashboard")["CSHARP_API_URL"]

    assert upstream["value"].startswith("https://")
    assert "forexai-csharp-api" in upstream["value"]


def test_gateway_and_python_services_are_wired_to_each_other(services):
    python_url = _env(services, "forexai-csharp-api")[
        "PythonApi__BaseUrl"
    ]["value"]

    assert "forexai-python-ai" in python_url

    # The gateway must carry a key, because the hosted Python service has
    # its X-API-Key guard enabled (AI_SERVICE_API_KEY is generated).
    api_key = _env(services, "forexai-csharp-api")["PythonApi__ApiKey"]

    assert api_key.get("sync") is False

    guard = _env(services, "forexai-python-ai")["AI_SERVICE_API_KEY"]

    assert guard.get("generateValue") is True
