"""Tests for mitol.observability.logging."""

import logging

import pytest
import structlog
from django.test import override_settings


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog configuration between tests."""
    yield
    structlog.reset_defaults()


@override_settings(DEBUG=True)
def test_configure_structlog_debug():
    """In DEBUG mode, structlog is configured with ConsoleRenderer."""
    from mitol.observability.logging import configure_structlog

    configure_structlog(debug=True)

    assert structlog.is_configured()
    config = structlog.get_config()
    processor_types = [type(p).__name__ for p in config["processors"]]
    assert "ConsoleRenderer" in processor_types


@override_settings(DEBUG=False)
def test_configure_structlog_production():
    """In production mode, structlog is configured with JSONRenderer."""
    from mitol.observability.logging import configure_structlog

    configure_structlog(debug=False)

    assert structlog.is_configured()
    config = structlog.get_config()
    processor_types = [type(p).__name__ for p in config["processors"]]
    assert "JSONRenderer" in processor_types
    assert "ConsoleRenderer" not in processor_types


@override_settings(DEBUG=False)
def test_stdlib_logging_routed(capfd):
    """After configuration, stdlib logging routes through structlog."""
    from mitol.observability.logging import configure_structlog

    configure_structlog(debug=False)

    logger = logging.getLogger("test.stdlib.routing")
    logger.warning("stdlib test message")

    captured = capfd.readouterr()
    # JSON output should contain the event
    assert (
        "stdlib test message" in captured.out or "stdlib test message" in captured.err
    )


@override_settings(DEBUG=False)
def test_configure_structlog_log_level_from_env(monkeypatch):
    """LOG_LEVEL env var controls the root logger level."""
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    from mitol.observability.logging import configure_structlog

    configure_structlog(debug=False)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
