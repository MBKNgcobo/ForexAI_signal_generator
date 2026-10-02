"""Shared pytest configuration.

The suite lives in ``tests/`` without an ``__init__.py``, so pytest's default
import mode would only put ``tests/`` on ``sys.path`` - which breaks imports
such as ``from tests.fakes.fake_llm import ...``. ``pyproject.toml`` already
sets ``pythonpath = ["."]``; this explicit guard keeps the suite working even
if it is run with an older pytest that ignores that setting.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
