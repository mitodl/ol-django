"""Tests for mitol.observability.logging."""

import json
import logging

import pytest
import structlog
from django.test import override_settings
from mitol.observability.logging import (
    _EXCEPTION_RENDERER,
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


# ---------------------------------------------------------------------------
# Exception rendering tests
# ---------------------------------------------------------------------------


@override_settings(DEBUG=False)
def test_exception_renderer_in_production_formatter_processors():
    """Production ProcessorFormatter.processors includes ExceptionRenderer."""
    configure_structlog(debug=False)

    root_handler = logging.getLogger().handlers[0]
    formatter = root_handler.formatter
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)

    processor_types = [type(p).__name__ for p in formatter.processors]
    assert "ExceptionRenderer" in processor_types


@override_settings(DEBUG=True)
def test_no_exception_renderer_in_debug_formatter_processors():
    """Debug ProcessorFormatter.processors does NOT need ExceptionRenderer.

    ConsoleRenderer handles exc_info natively, so adding ExceptionRenderer
    would consume exc_info before ConsoleRenderer can render it in colour.
    """
    configure_structlog(debug=True)

    root_handler = logging.getLogger().handlers[0]
    formatter = root_handler.formatter
    processor_types = [type(p).__name__ for p in formatter.processors]
    assert "ExceptionRenderer" not in processor_types


@override_settings(DEBUG=False)
def test_foreign_stdlib_exc_info_rendered_as_structured_dict(capfd):
    """Foreign stdlib records with exc_info produce a structured exception dict.

    This is the core regression test for the bug where exc_info was serialised
    as ["<class 'ValueError'>", "ValueError(...)", "<traceback object at 0x…>"].
    """
    configure_structlog(debug=False)

    try:
        raise ValueError("stdlib exception")  # noqa: TRY301, EM101, TRY003
    except ValueError:
        logging.getLogger("django.request").exception("request failed")

    captured = capfd.readouterr()
    output = captured.err or captured.out
    assert output.strip(), "Expected log output but got nothing"

    data = json.loads(output.strip())
    assert "exception" in data, (
        "Expected structured 'exception' key, got raw exc_info. "
        f"Keys present: {list(data.keys())}"
    )
    assert "exc_info" not in data, (
        "Raw exc_info tuple/list leaked into JSON output — "
        "ExceptionRenderer not applied"
    )


@override_settings(DEBUG=False)
def test_exception_dict_has_expected_structure(capfd):
    """Structured exception dict contains exc_type, exc_value, and frames."""
    configure_structlog(debug=False)

    try:
        raise RuntimeError("structured traceback test")  # noqa: TRY301, EM101, TRY003
    except RuntimeError:
        logging.getLogger("test").exception("caught it")

    captured = capfd.readouterr()
    output = captured.err or captured.out
    data = json.loads(output.strip())

    exception = data["exception"]
    assert isinstance(exception, list), "exception should be a list of exception dicts"
    entry = exception[0]
    assert entry["exc_type"] == "RuntimeError"
    assert "structured traceback test" in entry["exc_value"]
    assert isinstance(entry["frames"], list)


@override_settings(DEBUG=False)
def test_exception_dict_does_not_contain_locals(capfd):
    """show_locals=False: local variables must not appear in exception frames.

    Local variables can contain secrets, PII, or tokens; they must never be
    serialised into production logs.
    """
    configure_structlog(debug=False)

    secret_token = "super-secret-value-12345"  # noqa: S105

    try:
        raise ValueError("locals leak test")  # noqa: TRY301, EM101, TRY003
    except ValueError:
        logging.getLogger("test").exception("caught")

    captured = capfd.readouterr()
    output = captured.err or captured.out
    assert secret_token not in output, (
        "Local variable value leaked into log output — show_locals must be False"
    )

    data = json.loads(output.strip())
    for frame in data["exception"][0]["frames"]:
        assert not frame.get("locals"), (
            f"Frame {frame.get('name')} has locals present: {frame.get('locals')}"
        )


@override_settings(DEBUG=False)
def test_exception_renderer_is_shared_singleton():
    """_EXCEPTION_RENDERER is reused by configure_structlog and _make_formatter."""
    configure_structlog(debug=False)

    # Both code paths must use the same configured instance so that
    # show_locals and max_frames settings are consistent everywhere.
    root_handler = logging.getLogger().handlers[0]
    formatter = root_handler.formatter
    assert any(p is _EXCEPTION_RENDERER for p in formatter.processors)

    settings_formatter = _make_formatter()
    assert any(p is _EXCEPTION_RENDERER for p in settings_formatter.processors)


# ---------------------------------------------------------------------------
# force= / idempotency tests
# ---------------------------------------------------------------------------


@override_settings(DEBUG=False)
def test_configure_structlog_idempotent():
    """Calling configure_structlog() twice without force= is a no-op."""
    configure_structlog(debug=False)
    first_handler = logging.getLogger().handlers[0]

    configure_structlog(debug=False)
    second_handler = logging.getLogger().handlers[0]

    assert first_handler is second_handler


@override_settings(DEBUG=False)
def test_configure_structlog_force_reconfigures():
    """force=True re-runs configuration even when already configured."""
    configure_structlog(debug=False)
    first_handler = logging.getLogger().handlers[0]

    configure_structlog(debug=False, force=True)
    second_handler = logging.getLogger().handlers[0]

    # A new handler is installed; the config was genuinely re-applied.
    assert first_handler is not second_handler


# ---------------------------------------------------------------------------
# Celery / django-structlog logger configuration tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "logger_name",
    ["celery", "celery.task", "celery.worker", "django_structlog"],
)
@override_settings(DEBUG=False)
def test_celery_loggers_configured(logger_name):
    """Celery and django_structlog loggers are routed through the console handler."""
    configure_structlog(debug=False)

    logger = logging.getLogger(logger_name)
    # The logger must have a handler (either directly or via effective handler
    # lookup) that uses a structlog ProcessorFormatter.
    effective = logger
    while effective:
        if effective.handlers:
            handler = effective.handlers[0]
            assert isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter), (
                f"Logger '{logger_name}' handler does not use ProcessorFormatter"
            )
            return
        if not effective.propagate:
            break
        effective = effective.parent  # type: ignore[assignment]

    # No handler found — the logger must at least not propagate to a
    # misconfigured parent.
    pytest.fail(f"No structlog-formatted handler found for logger '{logger_name}'")
