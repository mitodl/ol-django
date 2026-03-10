"""Tests for mitol.observability.logging."""

import logging

import pytest
import structlog
from django.test import override_settings
from mitol.observability.logging import configure_structlog


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog configuration between tests."""
    yield
    structlog.reset_defaults()


@override_settings(DEBUG=True)
def test_configure_structlog_debug():
    """In DEBUG mode, pipeline ends with wrap_for_formatter; uses ConsoleRenderer."""
    configure_structlog(debug=True)

    assert structlog.is_configured()
    config = structlog.get_config()

    # The structlog pipeline must end with wrap_for_formatter so that stdlib
    # records are routed through the ProcessorFormatter renderer.
    assert (
        config["processors"][-1]
        is structlog.stdlib.ProcessorFormatter.wrap_for_formatter
    )

    # The root handler's ProcessorFormatter should use ConsoleRenderer.
    root_handler = logging.getLogger().handlers[0]
    assert isinstance(root_handler.formatter, structlog.stdlib.ProcessorFormatter)
    formatter_processor_types = [
        type(p).__name__ for p in root_handler.formatter.processors
    ]
    assert "ConsoleRenderer" in formatter_processor_types


@override_settings(DEBUG=False)
def test_configure_structlog_production():
    """In production mode, pipeline ends with wrap_for_formatter; uses JSONRenderer."""
    configure_structlog(debug=False)

    assert structlog.is_configured()
    config = structlog.get_config()

    # The structlog pipeline must end with wrap_for_formatter.
    assert (
        config["processors"][-1]
        is structlog.stdlib.ProcessorFormatter.wrap_for_formatter
    )

    # The root handler's ProcessorFormatter should use JSONRenderer.
    root_handler = logging.getLogger().handlers[0]
    assert isinstance(root_handler.formatter, structlog.stdlib.ProcessorFormatter)
    formatter_processor_types = [
        type(p).__name__ for p in root_handler.formatter.processors
    ]
    assert "JSONRenderer" in formatter_processor_types
    assert "ConsoleRenderer" not in formatter_processor_types


@override_settings(DEBUG=False)
def test_stdlib_logging_routed(capfd):
    """After configuration, stdlib logging routes through structlog."""
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

    configure_structlog(debug=False)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
