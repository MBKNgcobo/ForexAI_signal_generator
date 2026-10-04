"""Webhook allowlist matching and timeout configuration (SSRF guard).

The allowlist is the only thing standing between a public analysis endpoint
and an SSRF relay, so its matching rules are pinned here: bare entries stay
exact, wildcards cover subdomains, and no input can widen the list into
"any host".
"""

import pytest

from app.config import (
    DEFAULT_WEBHOOK_TIMEOUT_SECONDS,
    webhook_allowlist,
    webhook_timeout_seconds,
)
from app.services.webhook_delivery import webhook_allowed


@pytest.fixture(autouse=True)
def _clear_caches():
    webhook_allowlist.cache_clear()
    webhook_timeout_seconds.cache_clear()

    yield

    webhook_allowlist.cache_clear()
    webhook_timeout_seconds.cache_clear()


def _set_allowlist(monkeypatch, value: str) -> None:
    monkeypatch.setenv("WEBHOOK_ALLOWLIST", value)
    webhook_allowlist.cache_clear()


def test_exact_entry_matches_only_itself(monkeypatch):
    _set_allowlist(monkeypatch, "hooks.example.com")

    assert webhook_allowed("https://hooks.example.com/signal") is True
    # A subdomain of an exact entry must NOT be implied.
    assert webhook_allowed("https://evil.hooks.example.com/x") is False


def test_dot_wildcard_covers_subdomains_and_bare_domain(monkeypatch):
    _set_allowlist(monkeypatch, ".trycloudflare.com")

    assert webhook_allowed("https://random-words.trycloudflare.com/s") is True
    assert webhook_allowed("https://a.b.trycloudflare.com/s") is True
    assert webhook_allowed("https://trycloudflare.com/s") is True


def test_star_wildcard_is_equivalent_to_dot_wildcard(monkeypatch):
    _set_allowlist(monkeypatch, "*.trycloudflare.com")

    assert webhook_allowed("https://random.trycloudflare.com/s") is True
    assert webhook_allowed("https://trycloudflare.com/s") is True


def test_wildcard_does_not_match_a_neighbouring_domain(monkeypatch):
    """The suffix must be anchored on a dot.

    ``nottrycloudflare.com`` merely *ends with* the string
    ``trycloudflare.com``; allowing it would hand that domain to whoever
    registers it.
    """

    _set_allowlist(monkeypatch, ".trycloudflare.com")

    assert webhook_allowed("https://nottrycloudflare.com/s") is False
    assert webhook_allowed("https://trycloudflare.com.evil.net/s") is False


def test_bare_star_matches_nothing(monkeypatch):
    """``*`` must never degrade the guard into allow-all."""

    _set_allowlist(monkeypatch, "*")

    assert webhook_allowed("https://anything.example/x") is False


def test_wildcard_entry_without_a_domain_matches_nothing(monkeypatch):
    _set_allowlist(monkeypatch, "*.")

    assert webhook_allowed("https://anything.example/x") is False


def test_allowlist_is_case_insensitive(monkeypatch):
    _set_allowlist(monkeypatch, "Hooks.Example.COM")

    assert webhook_allowed("https://HOOKS.example.com/s") is True


def test_non_http_schemes_are_refused(monkeypatch):
    _set_allowlist(monkeypatch, ".trycloudflare.com")

    assert webhook_allowed("file:///etc/passwd") is False
    assert webhook_allowed("gopher://hooks.example.com/x") is False


def test_multiple_entries_are_all_honoured(monkeypatch):
    _set_allowlist(
        monkeypatch,
        " hooks.example.com , .trycloudflare.com , ",
    )

    assert webhook_allowed("https://hooks.example.com/s") is True
    assert webhook_allowed("https://x.trycloudflare.com/s") is True
    assert webhook_allowed("https://nope.example.org/s") is False


def test_empty_allowlist_denies_everything_but_localhost(monkeypatch):
    _set_allowlist(monkeypatch, "")

    assert webhook_allowed("https://evil.example/x") is False
    assert webhook_allowed("http://127.0.0.1:8799/signal") is True


def test_timeout_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("WEBHOOK_TIMEOUT_SECONDS", raising=False)

    assert webhook_timeout_seconds() == DEFAULT_WEBHOOK_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "raw",
    ["0", "-1", "not-a-number", ""],
)
def test_invalid_timeouts_fall_back_to_the_default(monkeypatch, raw):
    """A bad value must never disable the timeout guard."""

    monkeypatch.setenv("WEBHOOK_TIMEOUT_SECONDS", raw)

    assert webhook_timeout_seconds() == DEFAULT_WEBHOOK_TIMEOUT_SECONDS


def test_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("WEBHOOK_TIMEOUT_SECONDS", "8.5")

    assert webhook_timeout_seconds() == 8.5