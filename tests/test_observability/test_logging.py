"""Tests for mitol.observability.logging."""

import logging

import pytest
import structlog
from django.test import override_settings
from mitol.observability.logging import (
    _shared_processors,
    configure_structlog,
    reset_configuration,
)
from mitol.observability.settings.logging import _make_formatter


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog configuration and root logger state between tests."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level

    # Start each test with a clean slate
    reset_configuration()
    root.handlers.clear()

    yield

    # Restore original state after each test
    structlog.reset_defaults()
    reset_configuration()
    root.handlers = saved_handlers
    root.level = saved_level


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


@override_settings(DEBUG=False)
def test_make_formatter_has_foreign_pre_chain():
    """_make_formatter includes foreign_pre_chain so stdlib logs are enriched."""
    formatter = _make_formatter()

    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    assert formatter.foreign_pre_chain is not None
    assert len(formatter.foreign_pre_chain) > 0

    # The foreign_pre_chain must include the same processors as _shared_processors()
    # so that timestamps, log levels, and trace context are injected into all
    # foreign (non-structlog) log records from Django, boto3, etc.
    expected_chain = _shared_processors()
    assert len(formatter.foreign_pre_chain) == len(expected_chain)


@override_settings(DEBUG=False)
def test_make_formatter_production_uses_json_renderer():
    """In production (DEBUG=False), _make_formatter uses JSONRenderer."""
    formatter = _make_formatter()

    renderer_types = [type(p).__name__ for p in formatter.processors]
    assert "JSONRenderer" in renderer_types
    assert "ConsoleRenderer" not in renderer_types


@override_settings(DEBUG=True)
def test_make_formatter_debug_uses_console_renderer():
    """In debug mode (DEBUG=True), _make_formatter uses ConsoleRenderer."""
    formatter = _make_formatter()

    renderer_types = [type(p).__name__ for p in formatter.processors]
    assert "ConsoleRenderer" in renderer_types
    assert "JSONRenderer" not in renderer_types
