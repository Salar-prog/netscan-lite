"""Tests for logging and request ID middleware."""

import logging

from netscan_lite.logging_config import RequestIDFilter, request_id_var, setup_logging


def test_request_id_in_response_headers(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers


def test_custom_request_id_preserved(client):
    resp = client.get("/health", headers={"X-Request-ID": "my-custom-id"})
    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == "my-custom-id"


def test_request_id_filter():
    f = RequestIDFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    request_id_var.set("test-123")
    assert f.filter(record)
    assert record.request_id == "test-123"  # type: ignore[attr-defined]


def test_request_id_filter_default():
    f = RequestIDFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    request_id_var.set("")
    assert f.filter(record)
    assert record.request_id == ""  # type: ignore[attr-defined]


def test_setup_logging_configures_root():
    setup_logging(log_level="warning")
    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert len(root.handlers) == 1
