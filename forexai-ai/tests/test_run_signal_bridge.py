"""Safety interlock of the local signal-receiver script.

``scripts/run_signal_bridge.py`` used to arm real orders with ``--live``
alone, contradicting its own documented contract (``MT5_DRY_RUN=false``
required too). The dual-key rule is pinned here:

- ``--live`` + dry-run config  -> startup refused (exit 2)
- ``--live`` + ``MT5_DRY_RUN=false`` -> allowed (server start not tested
  here; it would bind a port and block)
- no ``--live`` (any config)   -> allowed, stays dry-run
"""

import sys

from scripts.run_signal_bridge import live_mode_refused
from scripts.run_signal_bridge import main as bridge_main


def test_refused_when_live_but_config_is_dry_run():
    # The historical bug: --live alone went live. Must be refused.
    assert live_mode_refused(live_flag=True, dry_run_value=True) is True


def test_allowed_when_live_and_config_disables_dry_run():
    assert live_mode_refused(live_flag=True, dry_run_value=False) is False


def test_dry_run_start_never_refused():
    # Both config states: a plain start must always work (default mode).
    assert live_mode_refused(live_flag=False, dry_run_value=True) is False
    assert live_mode_refused(live_flag=False, dry_run_value=False) is False


def test_main_refuses_live_flag_under_dry_run_config(monkeypatch):
    monkeypatch.setenv("MT5_DRY_RUN", "true")
    monkeypatch.setattr(sys, "argv", ["run_signal_bridge.py", "--live"])

    assert bridge_main() == 2
