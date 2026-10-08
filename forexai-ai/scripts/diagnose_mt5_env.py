"""Diagnose MT5 credential visibility WITHOUT printing secrets.

Prints only booleans (set/missing) and harmless metadata (lengths,
numeric-shape) so the output is safe to paste into tickets/screenshots.
Exit 0 when all three credential vars are visible, 2 otherwise.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _status(name: str) -> dict:
    raw = os.getenv(name)
    present = raw is not None and raw.strip().strip("\"'").strip() != ""
    cleaned = (raw or "").strip().strip("\"'").strip()
    info = {"name": name, "set": present, "length": len(cleaned) if present else 0}

    if name == "MT5_LOGIN" and present:
        info["numeric"] = cleaned.isdigit()

    if name == "MT5_SERVER" and present:
        info["has_whitespace"] = any(ch.isspace() for ch in cleaned)

    return info


def main() -> int:
    print("MT5 credential visibility (values NEVER printed):")

    ok = True

    for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER", "MT5_PATH"):
        info = _status(name)
        print(f"  {name}: set={info['set']} " + " ".join(f"{k}={v}" for k, v in info.items() if k not in ("name", "set")))

        if name != "MT5_PATH" and not info["set"]:
            ok = False

    if not ok:
        print("\nMissing: uncomment MT5_LOGIN/MT5_PASSWORD/MT5_SERVER in .env (no leading '#', no trailing spaces).")
        return 2

    print("\nAll credential vars visible to Python. Re-run check_mt5_connection.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
