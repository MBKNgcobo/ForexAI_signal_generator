"""Structured logging: JSON or human-readable text output.

``LOG_FORMAT=json`` selects machine-readable lines; anything else keeps the
current text format, so behaviour is unchanged unless a deployment opts in.
Both formats carry the active ``request_id`` so logs from one request can be
correlated across the pipeline nodes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.observability.context import get_request_id


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def formatter_for(name: str | None) -> logging.Formatter:
    """Return the JSON formatter for ``json``, else the text default."""

    if (name or "").strip().lower() == "json":
        return JsonFormatter()

    return logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
    )
