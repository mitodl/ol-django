"""Tests for mitol.observability.telemetry."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


def _reset_tracer_provider():
    """Reset global tracer provider between tests."""
    from opentelemetry.sdk.trace import TracerProvider

    trace.set_tracer_provider(TracerProvider())


@pytest.fixture(autouse=True)
def reset_otel():
    """Ensure a clean OTel state for each test."""
    yield
    _reset_tracer_provider()


@override_settings(DEBUG=False)
def test_configure_opentelemetry_no_endpoint_no_debug(monkeypatch):
    """Returns None when no endpoint configured and not DEBUG."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Reimport to get fresh state
    from mitol.observability.telemetry import configure_opentelemetry

    result = configure_opentelemetry()
    assert result is None


@override_settings(DEBUG=False)
def test_configure_opentelemetry_with_endpoint(monkeypatch):
    """Returns TracerProvider when OTLP endpoint is configured."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
    ):
        from mitol.observability.telemetry import configure_opentelemetry

        result = configure_opentelemetry()

    assert result is not None
    assert isinstance(result, TracerProvider)


@override_settings(DEBUG=True)
def test_configure_opentelemetry_debug_mode(monkeypatch):
    """In DEBUG mode, returns TracerProvider with ConsoleSpanExporter."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    from mitol.observability.telemetry import configure_opentelemetry

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
        from mitol.observability.telemetry import configure_opentelemetry

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
        from mitol.observability.telemetry import configure_opentelemetry

        # Should not raise
        result = configure_opentelemetry()

    assert result is not None
