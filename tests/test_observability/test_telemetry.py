"""Tests for mitol.observability.telemetry."""

from unittest.mock import MagicMock, patch

import mitol.observability.telemetry as telemetry_module
import opentelemetry.metrics._internal as metrics_internal
import opentelemetry.trace as trace_internal
import pytest
from django.test import override_settings
from mitol.observability.telemetry import (
    configure_opentelemetry,
    reset_configuration,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util._once import Once


def _reset_global_providers():
    """Clear the SDK's global tracer and meter providers.

    Reaching into private globals because there is no public way to do this:
    set_tracer_provider/set_meter_provider are guarded by a ``Once`` and simply
    log "Overriding of current X is not allowed" on a second call. Clearing the
    provider alone is not enough either -- the Once has to be replaced as well,
    or the next set is still swallowed.

    Without this the first test to configure telemetry pins the provider for the
    whole session and every later test silently gets that one instead of its
    own, which makes outcomes depend on execution order.

    Providers are shut down before being dropped. Clearing the global alone
    leaves the BatchSpanProcessor and PeriodicExportingMetricReader worker
    threads running with nothing able to reach them, so they accumulate across
    the suite and keep trying to export.
    """
    for provider in (
        trace_internal._TRACER_PROVIDER,  # noqa: SLF001
        metrics_internal._METER_PROVIDER,  # noqa: SLF001
    ):
        shutdown = getattr(provider, "shutdown", None)
        if shutdown is not None:
            shutdown()

    trace_internal._TRACER_PROVIDER = None  # noqa: SLF001
    trace_internal._TRACER_PROVIDER_SET_ONCE = Once()  # noqa: SLF001
    metrics_internal._METER_PROVIDER = None  # noqa: SLF001
    metrics_internal._METER_PROVIDER_SET_ONCE = Once()  # noqa: SLF001


@pytest.fixture(autouse=True)
def reset_otel():
    """Ensure a clean OTel state for each test."""
    _reset_global_providers()
    reset_configuration()
    yield
    _reset_global_providers()
    reset_configuration()


def _clear_otlp_env(monkeypatch):
    """Remove every OTLP endpoint variable configure_opentelemetry() consults.

    Any one of these left set puts a test at the mercy of the ambient
    environment, so this has to track the full set the guard checks -- traces
    and metrics both, not just the base variable.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)


@override_settings(DEBUG=False)
def test_configure_opentelemetry_no_endpoint_no_debug(monkeypatch):
    """Returns None when no endpoint configured and not DEBUG."""
    _clear_otlp_env(monkeypatch)

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
    _clear_otlp_env(monkeypatch)

    result = configure_opentelemetry()

    assert result is not None
    assert isinstance(result, TracerProvider)


@override_settings(DEBUG=True, OPENTELEMETRY_CONSOLE_EXPORTER=False)
def test_configure_opentelemetry_debug_mode_without_console_exporter(monkeypatch):
    """In DEBUG mode without console exporter, still returns TracerProvider."""
    _clear_otlp_env(monkeypatch)

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


@override_settings(DEBUG=False)
def test_base_endpoint_env_is_left_for_the_sdk_to_resolve(monkeypatch):
    """A base URL must not be handed to the exporter verbatim.

    An endpoint passed explicitly is used as-is, so forwarding the base URL
    would POST every batch to the collector root and 404.
    """
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    with patch("mitol.observability.telemetry.OTLPSpanExporter") as mock_exporter:
        assert configure_opentelemetry() is not None

    assert mock_exporter.call_args.kwargs["endpoint"] is None


@override_settings(DEBUG=False)
def test_signal_specific_endpoint_env_enables_tracing(monkeypatch):
    """OTEL_EXPORTER_OTLP_TRACES_ENDPOINT alone is enough to configure tracing.

    It previously fell through to the no-endpoint path and disabled tracing
    silently.
    """
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/v1/traces"
    )

    with patch("mitol.observability.telemetry.OTLPSpanExporter") as mock_exporter:
        assert configure_opentelemetry() is not None

    assert mock_exporter.call_args.kwargs["endpoint"] is None


@override_settings(
    DEBUG=False,
    OPENTELEMETRY_ENDPOINT="http://collector:4318/v1/traces",
)
def test_settings_endpoint_is_passed_verbatim(monkeypatch):
    """A Django-settings endpoint is a full signal URL, so it is used as given."""
    _clear_otlp_env(monkeypatch)

    with patch("mitol.observability.telemetry.OTLPSpanExporter") as mock_exporter:
        assert configure_opentelemetry() is not None

    assert (
        mock_exporter.call_args.kwargs["endpoint"] == "http://collector:4318/v1/traces"
    )


@override_settings(DEBUG=False)
def test_sdk_appends_the_signal_path_to_a_base_endpoint(monkeypatch):
    """Canary for the SDK behaviour the code above depends on.

    Reaches into a private attribute deliberately: if the SDK stops appending
    "/v1/traces" to OTEL_EXPORTER_OTLP_ENDPOINT, passing endpoint=None silently
    stops working and this is what says so.
    """
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    exporter = telemetry_module.OTLPSpanExporter(endpoint=None)

    assert exporter._endpoint == "http://collector:4318/v1/traces"  # noqa: SLF001


@override_settings(DEBUG=False, OPENTELEMETRY_USE_GRPC=True)
def test_grpc_endpoint_env_is_left_for_the_sdk_to_resolve(monkeypatch):
    """The gRPC exporter has the same verbatim-endpoint contract as HTTP."""
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

    with patch("mitol.observability.telemetry.GrpcExporter") as mock_exporter:
        assert configure_opentelemetry() is not None

    assert mock_exporter.call_args.kwargs["endpoint"] is None


@override_settings(
    DEBUG=False,
    OPENTELEMETRY_USE_GRPC=True,
    OPENTELEMETRY_ENDPOINT="http://collector:4317",
    OPENTELEMETRY_INSECURE=True,
)
def test_grpc_settings_endpoint_is_passed_verbatim(monkeypatch):
    """And a settings endpoint still reaches the gRPC exporter as given."""
    _clear_otlp_env(monkeypatch)

    with patch("mitol.observability.telemetry.GrpcExporter") as mock_exporter:
        assert configure_opentelemetry() is not None

    assert mock_exporter.call_args.kwargs["endpoint"] == "http://collector:4317"
    assert mock_exporter.call_args.kwargs["insecure"] is True


@override_settings(
    DEBUG=False, OPENTELEMETRY_ENDPOINT="http://collector:4318/v1/traces"
)
def test_metrics_stay_off_without_an_environment_endpoint(monkeypatch):
    """OPENTELEMETRY_ENDPOINT must not be reused for metrics.

    It is a full traces URL, so borrowing it would POST metrics to /v1/traces.
    """
    _clear_otlp_env(monkeypatch)

    with patch("mitol.observability.telemetry.MeterProvider") as mock_provider:
        assert configure_opentelemetry() is not None

    mock_provider.assert_not_called()


@override_settings(DEBUG=False)
def test_base_endpoint_env_configures_metrics(monkeypatch):
    """A base OTLP URL turns on metrics as well as traces."""
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    with (
        patch("mitol.observability.telemetry.OTLPSpanExporter"),
        patch("mitol.observability.telemetry.OTLPMetricExporter"),
        patch("mitol.observability.telemetry.MeterProvider") as mock_provider,
    ):
        assert configure_opentelemetry() is not None

    mock_provider.assert_called_once()


@override_settings(DEBUG=False)
def test_meter_provider_is_installed_before_instrumentors_run(monkeypatch):
    """Pins the intended ordering, so instrumentors get real instruments.

    Not a correctness requirement: get_meter() hands out proxy instruments that
    rebind when a provider appears later, and they do forward records
    afterwards (checked against opentelemetry-instrumentation-django 0.65b0 --
    a late provider install still collected http.server.duration). Ordering it
    this way just avoids depending on that rebinding.
    """
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    calls = []

    with (
        patch("mitol.observability.telemetry.OTLPSpanExporter"),
        patch("mitol.observability.telemetry.OTLPMetricExporter"),
        patch(
            "mitol.observability.telemetry.metrics.set_meter_provider",
            side_effect=lambda _p: calls.append("meter_provider"),
        ),
        patch(
            "mitol.observability.telemetry._auto_instrument",
            side_effect=lambda: calls.append("auto_instrument"),
        ),
    ):
        configure_opentelemetry()

    assert calls == ["meter_provider", "auto_instrument"]


@override_settings(DEBUG=False)
def test_metrics_only_endpoint_still_configures_metrics(monkeypatch):
    """A metrics-only endpoint must not be swallowed by the traces guard.

    The early return keys off the traces endpoint, so before this it returned
    before _configure_metrics ever ran.
    """
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector:4318/v1/metrics"
    )

    with (
        patch("mitol.observability.telemetry.OTLPMetricExporter"),
        patch("mitol.observability.telemetry.MeterProvider") as mock_provider,
    ):
        assert configure_opentelemetry() is not None

    mock_provider.assert_called_once()


@override_settings(
    DEBUG=False, OPENTELEMETRY_USE_GRPC=True, OPENTELEMETRY_INSECURE=True
)
def test_metrics_follow_the_grpc_transport_setting(monkeypatch):
    """Sharing a base endpoint means an HTTP exporter would hit a gRPC port."""
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

    with (
        patch("mitol.observability.telemetry.GrpcExporter"),
        patch("mitol.observability.telemetry.OTLPMetricExporter") as http_exporter,
        patch("mitol.observability.telemetry.GrpcMetricExporter") as grpc_exporter,
        patch("mitol.observability.telemetry.MeterProvider"),
    ):
        assert configure_opentelemetry() is not None

    grpc_exporter.assert_called_once()
    http_exporter.assert_not_called()


@override_settings(DEBUG=False)
def test_metrics_failure_does_not_stop_the_service_starting(monkeypatch):
    """This runs from AppConfig.ready(); raising here means the app will not boot."""
    _clear_otlp_env(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    with (
        patch("mitol.observability.telemetry.OTLPSpanExporter"),
        patch(
            "mitol.observability.telemetry.OTLPMetricExporter",
            side_effect=ValueError("bad metrics config"),
        ),
    ):
        assert configure_opentelemetry() is not None
