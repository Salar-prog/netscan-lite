"""Structured logging configuration with request ID context and audit logging."""

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

_audit_logger = logging.getLogger("ns-lite.audit")


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

    # Audit logger: always structured JSON, writes to stderr (separate stream)
    audit_handler = logging.StreamHandler(sys.stderr)
    audit_handler.setLevel(logging.INFO)
    try:
        from pythonjsonlogger.json import JsonFormatter

        audit_handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    except ImportError:
        audit_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _audit_logger.addHandler(audit_handler)
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False


def audit(action: str, *, user: str = "-", detail: str = "", result: str = "ok") -> None:
    """Write a structured audit log entry.

    Every API call, CLI command, and scanner operation goes through here.
    Fields: action, user, detail, result, request_id.
    """
    req_id = request_id_var.get("")
    _audit_logger.info(
        "action=%s user=%s result=%s request_id=%s %s",
        action,
        user,
        result,
        req_id,
        detail,
    )
