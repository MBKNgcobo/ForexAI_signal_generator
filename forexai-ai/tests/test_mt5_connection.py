"""MT5 connection lifecycle (Phase 1): hermetic, no terminal required."""

import sys
import types

import pytest

from app.broker import mt5_connection
from app.broker.mt5_connection import (
    MT5ConnectionError,
    connect,
    ensure_terminal_running,
    shutdown,
)


def _install_fake_mt5(monkeypatch, **overrides):
    """Inject a fake MetaTrader5 module so no terminal is touched."""

    calls = {"shutdown": 0}

    defaults = {
        "initialize": lambda **kwargs: True,
        "login": lambda *a, **k: True,
        "account_info": lambda: types.SimpleNamespace(
            login=12345,
            server="Demo-Server",
            balance=10000.0,
            equity=10050.0,
            currency="USD",
            trade_allowed=True,
        ),
        "last_error": lambda: (1, "ok"),
        "shutdown": lambda: calls.__setitem__("shutdown", 1),
    }
    defaults.update(overrides)

    fake = types.SimpleNamespace(**defaults)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    return fake, calls


@pytest.fixture
def _terminal_ok(monkeypatch, tmp_path):
    """Fake an installed terminal with a running process."""

    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(
        mt5_connection, "_terminal_process_running", lambda: True
    )
    return str(exe)


def test_connect_success(monkeypatch, _terminal_ok):
    _install_fake_mt5(monkeypatch)

    account = connect(
        login=12345, password="pw", server="Demo-Server", path=_terminal_ok
    )

    assert account.login == 12345
    assert account.balance == 10000.0
    assert account.trade_allowed is True


def test_missing_package_is_actionable(monkeypatch, tmp_path):
    # ``None`` in sys.modules makes `import MetaTrader5` raise
    # ImportError deterministically, regardless of whether the real
    # package is installed (and of Python's import-statement internals).
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)

    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(
        mt5_connection, "_terminal_process_running", lambda: True
    )

    with pytest.raises(MT5ConnectionError, match="not installed"):
        connect(login=1, password="x", server="s", path=str(exe))


def test_missing_terminal_executable(monkeypatch, tmp_path):
    with pytest.raises(MT5ConnectionError, match="not found"):
        ensure_terminal_running(str(tmp_path / "nope.exe"))


def test_login_rejected_reports_last_error(monkeypatch, _terminal_ok):
    _install_fake_mt5(
        monkeypatch,
        login=lambda *a, **k: False,
        last_error=lambda: (10004, "account disabled"),
    )

    with pytest.raises(MT5ConnectionError, match="10004"):
        connect(
            login=12345,
            password="bad",
            server="Demo-Server",
            path=_terminal_ok,
        )


def test_initialize_false_is_actionable(monkeypatch, _terminal_ok):
    _install_fake_mt5(
        monkeypatch,
        initialize=lambda **kwargs: False,
        last_error=lambda: (2, "ipc not ready"),
    )

    with pytest.raises(MT5ConnectionError, match="ipc not ready"):
        connect(
            login=12345,
            password="pw",
            server="Demo-Server",
            path=_terminal_ok,
        )


def test_shutdown_without_package_is_safe(monkeypatch):
    # See test_missing_package_is_actionable for why None-injection is
    # the reliable way to make the lazy import fail.
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)

    shutdown()  # must not raise


def test_attach_mode_reuses_terminal_session(monkeypatch, _terminal_ok):
    """login=None must attach without calling mt5.login."""

    fake, _ = _install_fake_mt5(monkeypatch)
    login_calls = []
    fake.login = lambda *a, **k: login_calls.append(a) or True

    account = connect(path=_terminal_ok)  # no credentials

    assert login_calls == []  # attach path: no re-login attempted
    assert account.login == 12345
    assert account.server == "Demo-Server"


def test_attach_mode_without_session_raises(monkeypatch, _terminal_ok):
    _install_fake_mt5(monkeypatch, account_info=lambda: None)

    with pytest.raises(MT5ConnectionError, match="active trading"):
        connect(path=_terminal_ok)
