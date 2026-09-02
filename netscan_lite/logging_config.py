"""Structured logging configuration with request ID context."""

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]
        return True


def setup_logging(log_level: str = "info", json_format: bool = False) -> None:
    """Configure structured logging with request IDs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())

    if json_format:
        try:
            from pythonjsonlogger.json import JsonFormatter

            formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s")
        except ImportError:
            formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper()))
