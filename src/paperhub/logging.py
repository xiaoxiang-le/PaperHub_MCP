import json
import logging
import sys
from typing import Any


class SafeJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # An allowlist is stronger than trying to redact arbitrary provider text.
        result: dict[str, Any] = {
            "level": record.levelname,
            "event": record.msg if record.msg in {"tool_error", "started", "stopped"} else "event",
        }
        for key in ("tool", "code", "task_id", "exception_type"):
            if hasattr(record, key):
                result[key] = getattr(record, key)
        return json.dumps(result, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("paperhub")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(SafeJSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
