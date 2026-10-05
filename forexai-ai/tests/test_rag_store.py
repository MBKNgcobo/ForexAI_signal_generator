"""Connection settings for the fundamentals RAG store.

The store had no coverage at all, which is how a deployment reached Neon
without ``sslmode`` and failed on every analysis with::

    ERROR:  connection is insecure (try using `sslmode=require`)

libpq defaults to "prefer", so the failure only appears once the connection
reaches a database that refuses plaintext - after the host, user and
password are all correct, which makes it easy to misattribute.
"""

from app.config import (
    rag_db_hostaddr,
    rag_db_sslmode,
)
from app.fundamentals.rag_store import FundamentalRAGStore


def _store_kwargs(monkeypatch) -> dict:
    """Build the store's connection kwargs with the caches cleared."""

    rag_db_sslmode.cache_clear()
    rag_db_hostaddr.cache_clear()

    try:
        return FundamentalRAGStore().connection_kwargs.copy()
    finally:
        rag_db_sslmode.cache_clear()
        rag_db_hostaddr.cache_clear()


def test_connection_requires_tls_by_default(monkeypatch):
    """The regression: no sslmode meant plaintext was attempted first."""

    monkeypatch.delenv("RAG_DB_SSLMODE", raising=False)

    assert _store_kwargs(monkeypatch)["sslmode"] == "require"


def test_sslmode_can_be_overridden_for_local_postgres(monkeypatch):
    """docker compose Postgres has no TLS, so the value stays overridable."""

    monkeypatch.setenv("RAG_DB_SSLMODE", "disable")

    assert _store_kwargs(monkeypatch)["sslmode"] == "disable"


def test_blank_sslmode_falls_back_to_require(monkeypatch):
    monkeypatch.setenv("RAG_DB_SSLMODE", "   ")

    assert _store_kwargs(monkeypatch)["sslmode"] == "require"


def test_hostaddr_is_unset_by_default(monkeypatch):
    """DNS stays in charge unless an operator pins an address."""

    monkeypatch.delenv("RAG_DB_HOSTADDR", raising=False)

    assert _store_kwargs(monkeypatch)["hostaddr"] is None


def test_hostaddr_can_be_pinned(monkeypatch):
    monkeypatch.setenv("RAG_DB_HOSTADDR", " 52.14.39.200 ")

    assert _store_kwargs(monkeypatch)["hostaddr"] == "52.14.39.200"


def test_connection_reads_the_rag_db_variables(monkeypatch):
    monkeypatch.setenv("RAG_DB_HOST", "db.example.com")
    monkeypatch.setenv("RAG_DB_PORT", "6543")
    monkeypatch.setenv("RAG_DB_NAME", "forexai")
    monkeypatch.setenv("RAG_DB_USER", "neondb_owner")
    monkeypatch.setenv("RAG_DB_PASSWORD", "secret")

    kwargs = _store_kwargs(monkeypatch)

    assert kwargs["host"] == "db.example.com"
    assert kwargs["port"] == 6543
    assert kwargs["dbname"] == "forexai"
    assert kwargs["user"] == "neondb_owner"
    assert kwargs["password"] == "secret"