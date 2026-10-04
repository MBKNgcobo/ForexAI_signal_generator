"""The dashboard's nginx template is a deployment contract too.

It is rendered at container start by envsubst and, on Render, proxies to
the API over HTTPS. A ``location`` that forgets ``proxy_ssl_server_name on;``
does not fail at build time or at startup: nginx accepts the config, then
every proxied request dies with

    SSL_do_handshake() failed (SSL: error:0A000410 ... SSL alert number 40)

which Render's health checker sees as a 502, and the dashboard is restarted
in a loop until the deploy times out. That is exactly what happened once
already: ``/api/`` had the directive and ``/health`` did not, so the health
check failed while the API proxy was fine.

These tests parse the template and assert the invariants structurally, so a
new location cannot silently ship without them.
"""

from pathlib import Path

import pytest

#: forexai-ai/tests/ -> forexai-ai/ -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = (
    REPO_ROOT / "forexai-dashboard" / "templates" / "default.conf.template"
)


@pytest.fixture(scope="module")
def template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _configured_upstream() -> str:
    """The CSHARP_API_URL the dashboard is deployed with.

    Read from render.yaml because the template itself only holds the
    ``${CSHARP_API_URL}`` placeholder; the scheme that decides whether SNI
    is required lives in the blueprint.
    """

    import yaml

    blueprint = yaml.safe_load(
        (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    )

    for service in blueprint["services"]:
        if service["name"] != "forexai-dashboard":
            continue

        for entry in service.get("envVars", []):
            if entry["key"] == "CSHARP_API_URL":
                return entry["value"]

    raise AssertionError("CSHARP_API_URL is not declared in render.yaml")


def _locations(template: str) -> list[tuple[str, list[str]]]:
    """Return ``(directives, body)`` for each ``location`` block.

    Braces are not nested inside these blocks, so a simple scan is enough
    and keeps the test free of an nginx parser dependency.
    """

    blocks: list[tuple[str, list[str]]] = []
    lines = template.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip().startswith("location "):
            directives: list[str] = []
            index += 1

            while index < len(lines) and lines[index].strip() != "}":
                directives.append(lines[index].strip())
                index += 1

            blocks.append((line.strip(), directives))

        index += 1

    return blocks


def _is_comment(directive: str) -> bool:
    return directive.startswith("#")


def test_template_exists_and_renders_an_upstream(template):
    # ${CSHARP_API_URL} is substituted by envsubst at container start; the
    # literal placeholder must survive in the template itself.
    assert "${CSHARP_API_URL}" in template


def test_every_location_was_parsed(template):
    locations = _locations(template)

    assert len(locations) >= 3, (
        f"expected the SPA root, /api/ and /health; found {locations}"
    )


def test_proxied_locations_declare_the_upstream_url(template):
    """Every proxy_pass must target the configured API base URL."""

    proxied = [
        directives
        for _, directives in _locations(template)
        if any(
            directive.startswith("proxy_pass ")
            for directive in directives
            if not _is_comment(directive)
        )
    ]

    assert proxied, "no proxy_pass found - the dashboard would not proxy /api"

    for directives in proxied:
        pass_lines = [
            directive
            for directive in directives
            if directive.startswith("proxy_pass ")
        ]

        assert all(
            "${CSHARP_API_URL}" in line for line in pass_lines
        ), f"hardcoded upstream in {pass_lines}"


def test_health_probe_is_answered_locally(template):
    """The regression: /health proxied to a sleeping free-tier service.

    Render probes ``healthCheckPath`` on a fixed interval. While that
    location proxied to ``forexai-csharp-api``, a free-tier service that had
    spun down after its idle window forced a ~50 s cold start. Render's
    checker abandoned the request before nginx could answer, and because no
    response was ever written nginx logged ``499`` (client closed the
    connection) rather than a status code. That repeated every 10 s, the
    dashboard never went healthy, and the deploy ended in a restart loop
    until it timed out.

    A liveness probe may only assert what *this* service can vouch for -
    that nginx is up and serving. Whether the API is reachable is the API's
    own health check's job (``render.yaml`` -> ``forexai-csharp-api``,
    ``healthCheckPath: /health``).
    """

    blocks = [
        (name, directives)
        for name, directives in _locations(template)
        if "/health" in name
    ]

    assert len(blocks) == 1, (
        "expected exactly one /health location (exact or prefix match); "
        f"found {[name for name, _ in blocks]}"
    )

    name, directives = blocks[0]

    active = [
        directive
        for directive in directives
        if not _is_comment(directive)
    ]

    offenders = [
        directive
        for directive in active
        if directive.startswith("proxy_")
    ]

    assert not offenders, (
        f"{name} is the dashboard's own liveness probe and must not depend on "
        f"a downstream service, but these directives proxy it: {offenders}. "
        "Return a static 200 instead - the API has its own health check."
    )

    assert any(
        directive.startswith("return 200") for directive in active
    ), (
        f"{name} must return a static 200 so nginx always has a response to "
        f"write; its active directives were {active}"
    )


def test_health_probe_uses_an_exact_match(template):
    """``location = /health`` so the SPA cannot answer the probe.

    A prefix ``location /health`` also captures ``/healthz`` and
    ``/healthcheck``; exact matching keeps the probe unambiguous.
    """

    health = [
        name
        for name, _ in _locations(template)
        if "/health" in name
    ]

    assert all(
        name.startswith("location = ") for name in health
    ), (
        f"health probe must be an exact-match location: {health}"
    )


def test_every_https_proxy_sends_sni(template):
    """The regression: /health proxied to https without SNI.

    Render's edge answers an SNI-less TLS ClientHello with alert 40
    (handshake_failure), so nginx returns 502 for every request.

    Whether the upstream is https cannot be read from the template - it only
    contains the ``${CSHARP_API_URL}`` placeholder - so the scheme comes from
    the blueprint that configures it.
    """

    upstream = _configured_upstream()
    is_https = upstream.startswith("https://")

    offenders = []

    for name, directives in _locations(template):
        active = [
            directive
            for directive in directives
            if not _is_comment(directive)
        ]

        proxies = any(
            directive.startswith("proxy_pass ")
            for directive in active
        )

        if not (is_https and proxies):
            continue

        if "proxy_ssl_server_name on;" not in active:
            offenders.append(name)

    assert not offenders, (
        f"upstream {upstream} is https, but these proxying locations send "
        f"no SNI: {offenders}. Add 'proxy_ssl_server_name on;' or the "
        f"upstream will reject the TLS handshake (SSL alert number 40)."
    )


def test_sni_locations_also_pin_the_certificate_name(template):
    """``proxy_ssl_name`` keeps verification meaningful.

    Without it nginx still defaults to the proxy_pass host, but stating it
    explicitly is what makes the SNI and the expected certificate name the
    same value - the two can drift apart when the upstream URL changes.
    """

    offenders = []

    for name, directives in _locations(template):
        active = [
            directive
            for directive in directives
            if not _is_comment(directive)
        ]

        if "proxy_ssl_server_name on;" not in active:
            continue

        if "proxy_ssl_name $proxy_host;" not in active:
            offenders.append(name)

    assert not offenders, (
        f"SNI enabled without proxy_ssl_name: {offenders}"
    )


def test_nginx_runtime_variables_are_not_envsubst_targets(template):
    """The entrypoint substitutes *environment* variables only.

    If any nginx variable were written as ${...} it could be blanked out by
    envsubst, producing a config nginx refuses to load.
    """

    import re

    runtime = re.findall(r"\$\{([a-z_]+)\}", template)
    allowed = {"CSHARP_API_URL"}

    assert set(runtime) <= allowed, (
        f"unexpected ${{...}} placeholders: {set(runtime) - allowed}"
    )
