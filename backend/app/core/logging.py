import logging
import re
from typing import Any

_SECRET_KEYS = re.compile(r"pass(word)?|token|secret|api[_-]?key|authorization|cookie", re.IGNORECASE)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "***" if _SECRET_KEYS.search(str(k)) else _redact(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_redact(v) for v in value)
    if isinstance(value, str):
        return _BEARER.sub("Bearer ***", value)
    return value


class RedactingFilter(logging.Filter):
    """Masks secret-looking keys and bearer tokens in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _BEARER.sub("Bearer ***", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = _redact(record.args)
            else:
                record.args = tuple(_redact(a) for a in record.args)
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(RedactingFilter())
    for handler in root.handlers:
        handler.addFilter(RedactingFilter())
