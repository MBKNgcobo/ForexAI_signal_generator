"""MT5 terminal connection management (Phase 1)."""

from __future__ import annotations

import logging
import importlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
DEFAULT_TIMEOUT_SECONDS = 60.0


class MT5ConnectionError(RuntimeError):
    """Terminal unreachable, login failed, or IPC broke down."""


@dataclass(frozen=True)
class MT5AccountInfo:
    """Minimal account snapshot returned by ``connect`` (no secrets)."""

    login: int
    server: str
    balance: float
    equity: float
    currency: str
    trade_allowed: bool


def _import_mt5() -> Any:
    """Import the Windows-only package or raise an actionable error."""

    try:
        mt5 = importlib.import_module("MetaTrader5")
    except ImportError as exc:
        raise MT5ConnectionError(
            "The 'MetaTrader5' package is not installed. "
            "Install it on Windows with: pip install MetaTrader5. "
            "(It is Windows-only and intentionally absent on Linux.)"
        ) from exc

    return mt5


def _terminal_process_running() -> bool:
    """True when a terminal64.exe process is visible on this machine."""

    try:
        output = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MT5ConnectionError(
            f"Could not query running processes: {exc}"
        ) from exc

    return "terminal64.exe" in output.stdout.lower()


def ensure_terminal_running(
    path: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Ensure the terminal process exists; launch it if absent."""

    terminal = path or DEFAULT_TERMINAL_PATH

    if not Path(terminal).is_file():
        raise MT5ConnectionError(
            f"MT5 terminal not found at: {terminal}. "
            "Install MetaTrader 5 or set MT5_PATH to terminal64.exe."
        )

    if _terminal_process_running():
        logger.info("MT5 terminal process already running.")
        return terminal

    logger.info("Launching MT5 terminal: %s", terminal)

    try:
        subprocess.Popen(
            [terminal],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise MT5ConnectionError(
            f"Failed to launch MT5 terminal at {terminal}: {exc}"
        ) from exc

    deadline = time.monotonic() + max(1.0, timeout_seconds)

    while time.monotonic() < deadline:
        if _terminal_process_running():
            logger.info("MT5 terminal process detected.")
            return terminal

        time.sleep(2.0)

    raise MT5ConnectionError(
        f"MT5 terminal did not appear within {timeout_seconds:.0f}s "
        f"after launch from {terminal}."
    )


def _account_snapshot(
    mt5: Any,
    info: Any,
    fallback_login: int | None,
    fallback_server: str,
) -> MT5AccountInfo:
    """Build and log an ``MT5AccountInfo`` from ``account_info()``."""

    account = MT5AccountInfo(
        login=int(getattr(info, "login", fallback_login or 0)),
        server=str(getattr(info, "server", fallback_server) or ""),
        balance=float(getattr(info, "balance", 0.0) or 0.0),
        equity=float(getattr(info, "equity", 0.0) or 0.0),
        currency=str(getattr(info, "currency", "") or ""),
        trade_allowed=bool(getattr(info, "trade_allowed", False)),
    )

    logger.info(
        "MT5 connected: login=%s server=%s balance=%.2f %s trade_allowed=%s.",
        account.login,
        account.server,
        account.balance,
        account.currency,
        account.trade_allowed,
    )

    return account


def connect(
    login: int | None = None,
    password: str = "",
    server: str = "",
    path: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> MT5AccountInfo:
    """Initialize IPC; log in when credentials are given (attach otherwise).

    ``login`` provided: full ``initialize`` + ``login`` flow (safe for
    unattended use). ``login=None``: *attach mode* — connects to the
    session of an already open, logged-in terminal, so local dry-runs
    work when you are signed into MT5 without putting credentials in
    the environment. Any failure raises ``MT5ConnectionError`` with
    ``mt5.last_error()`` attached.
    """

    mt5 = _import_mt5()
    terminal = ensure_terminal_running(path, timeout_seconds)

    logger.info(
        "Initializing MT5 IPC (server: %s, login: %s).",
        server or "<terminal session>",
        login if login is not None else "<attach>",
    )

    try:
        if login is None:
            # Attach: reuse the terminal's active session.
            initialized = mt5.initialize(
                path=terminal,
                timeout=int(timeout_seconds * 1000),
            )
        else:
            initialized = mt5.initialize(
                path=terminal,
                login=login,
                password=password,
                server=server,
                timeout=int(timeout_seconds * 1000),
            )
    except Exception as exc:
        raise MT5ConnectionError(
            f"mt5.initialize raised {type(exc).__name__}: {exc}. "
            f"Terminal last_error={mt5.last_error()}"
        ) from exc

    if not initialized:
        raise MT5ConnectionError(
            "mt5.initialize returned False; the terminal is not ready. "
            f"last_error={mt5.last_error()}. "
            "Check the terminal is open, logged in, and Algo Trading "
            "is enabled."
        )

    if login is None:
        info = mt5.account_info()

        if info is None:
            mt5.shutdown()
            raise MT5ConnectionError(
                "Attach mode: the terminal has no active trading "
                f"session. Log into the terminal first. "
                f"last_error={mt5.last_error()}"
            )

        return _account_snapshot(mt5, info, fallback_login=None,
                                 fallback_server="")

    try:
        authorized = mt5.login(login, password=password, server=server)
    except Exception as exc:
        mt5.shutdown()
        raise MT5ConnectionError(
            f"mt5.login raised {type(exc).__name__}: {exc}. "
            f"Terminal last_error={mt5.last_error()}"
        ) from exc

    if not authorized:
        mt5.shutdown()
        raise MT5ConnectionError(
            f"MT5 login rejected for login={login} server={server}. "
            f"last_error={mt5.last_error()}. "
            "Verify credentials and that the account is a demo account."
        )

    info = mt5.account_info()

    if info is None:
        mt5.shutdown()
        raise MT5ConnectionError(
            "Login succeeded but account_info() returned None. "
            f"last_error={mt5.last_error()}"
        )

    return _account_snapshot(mt5, info, login, server)


def shutdown() -> None:
    """Release the IPC handle. Safe to call when never connected."""

    try:
        mt5 = _import_mt5()
    except MT5ConnectionError:
        logger.debug("MT5 shutdown skipped: package not installed.")
        return

    try:
        mt5.shutdown()
    except Exception as exc:
        logger.warning("MT5 shutdown raised %s: %s", type(exc).__name__, exc)
        return

    logger.info("MT5 IPC connection closed.")

