"""Tests for mitol.observability.telemetry."""

from unittest.mock import MagicMock, patch

import mitol.observability.telemetry as telemetry_module
import pytest
from django.test import override_settings
from mitol.observability.telemetry import (
    configure_opentelemetry,
    reset_configuration,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


def _reset_tracer_provider():
    """Reset global tracer provider between tests."""
    trace.set_tracer_provider(TracerProvider())


@pytest.fixture(autouse=True)
def reset_otel():
    """Ensure a clean OTel state for each test."""
    reset_configuration()
    yield
    _reset_tracer_provider()
    reset_configuration()


@override_settings(DEBUG=False)
def test_configure_opentelemetry_no_endpoint_no_debug(monkeypatch):
    """Returns None when no endpoint configured and not DEBUG."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    result = configure_opentelemetry()
    assert result is None


@override_settings(DEBUG=False)
def test_configure_opentelemetry_with_endpoint(monkeypatch):
    """Returns TracerProvider when OTLP endpoint is configured."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
    ):
        result = configure_opentelemetry()

    assert result is not None
    assert isinstance(result, TracerProvider)


@override_settings(DEBUG=True, OPENTELEMETRY_CONSOLE_EXPORTER=True)
def test_configure_opentelemetry_debug_mode_with_console_exporter(monkeypatch):
    """In DEBUG mode with console exporter enabled, returns TracerProvider."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    result = configure_opentelemetry()

    assert result is not None
    assert isinstance(result, TracerProvider)


@override_settings(DEBUG=True, OPENTELEMETRY_CONSOLE_EXPORTER=False)
def test_configure_opentelemetry_debug_mode_without_console_exporter(monkeypatch):
    """In DEBUG mode without console exporter, still returns TracerProvider."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    result = configure_opentelemetry()

    assert result is not None
    assert isinstance(result, TracerProvider)


@override_settings(DEBUG=False, MITOL_OBSERVABILITY_SKIP_INSTRUMENTORS={"django"})
def test_auto_instrument_skips(monkeypatch):
    """Skipped instrumentors are not loaded."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    mock_ep = MagicMock()
    mock_ep.name = "django"

    with (
        patch("importlib.metadata.entry_points", return_value=[mock_ep]),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
    ):
        configure_opentelemetry()

    mock_ep.load.assert_not_called()


@override_settings(DEBUG=False)
def test_auto_instrument_failure_does_not_raise(monkeypatch):
    """A failing instrumentor logs a warning but doesn't prevent OTel setup."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    mock_ep = MagicMock()
    mock_ep.name = "broken-lib"
    mock_ep.load.return_value = MagicMock(side_effect=Exception("boom"))

    with (
        patch("importlib.metadata.entry_points", return_value=[mock_ep]),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
    ):
        result = configure_opentelemetry()

    assert result is not None


@override_settings(DEBUG=False)
def test_configure_opentelemetry_idempotent(monkeypatch):
    """Multiple calls to configure_opentelemetry are idempotent."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
    ):
        result1 = configure_opentelemetry()
        assert result1 is not None

        assert telemetry_module._configured is True  # noqa: SLF001

        result2 = configure_opentelemetry()

    assert result2 is not None
    assert telemetry_module._configured is True  # noqa: SLF001


@override_settings(DEBUG=False)
def test_auto_instrument_idempotent(monkeypatch):
    """Auto-instrumentation runs only once even if called multiple times."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    mock_ep = MagicMock()
    mock_ep.name = "test-lib"
    mock_instrumentor_instance = MagicMock()
    mock_ep.load.return_value = MagicMock(return_value=mock_instrumentor_instance)

    with (
        patch(
            "mitol.observability.telemetry.importlib.metadata.entry_points",
            return_value=[mock_ep],
        ),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
    ):
        configure_opentelemetry()
        assert telemetry_module._instrumented is True  # noqa: SLF001

        telemetry_module._configured = False  # noqa: SLF001
        configure_opentelemetry()

    mock_instrumentor_instance.instrument.assert_called_once()


@override_settings(
    DEBUG=False,
    MITOL_OBSERVABILITY_ALLOW_INSTRUMENTORS={"allowed-lib"},
)
def test_auto_instrument_allowlist(monkeypatch):
    """Only allowlisted instrumentors are loaded when allowlist is set."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    allowed_ep = MagicMock()
    allowed_ep.name = "allowed-lib"
    mock_instrumentor_instance = MagicMock()
    allowed_ep.load.return_value = MagicMock(return_value=mock_instrumentor_instance)

    blocked_ep = MagicMock()
    blocked_ep.name = "blocked-lib"

    with (
        patch(
            "mitol.observability.telemetry.importlib.metadata.entry_points",
            return_value=[allowed_ep, blocked_ep],
        ),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
    ):
        configure_opentelemetry()

    mock_instrumentor_instance.instrument.assert_called_once()
    blocked_ep.load.assert_not_called()
