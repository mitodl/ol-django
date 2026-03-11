"""OpenTelemetry configuration for Django applications."""

from __future__ import annotations

import importlib.metadata
import logging
import os

from django.conf import settings
from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GrpcExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

log = logging.getLogger(__name__)

# Idempotency guards prevent double-instrumentation under Django autoreload
# or test setups that call ready() multiple times
_configured = False
_instrumented = False


def _get_resource() -> Resource:
    """Build OTel Resource from environment and Django settings."""
    attributes: dict[str, str] = {
        "service.name": (
            os.environ.get("OTEL_SERVICE_NAME")
            or getattr(settings, "OPENTELEMETRY_SERVICE_NAME", None)
            or "unknown"
        ),
        "service.version": getattr(settings, "VERSION", "unknown"),
        "deployment.environment": getattr(settings, "ENVIRONMENT", "unknown"),
    }
    # Kubernetes metadata — only include if present
    k8s_map = {
        "k8s.pod.name": os.environ.get("KUBERNETES_POD_NAME"),
        "k8s.namespace.name": os.environ.get("KUBERNETES_NAMESPACE"),
        "k8s.node.name": os.environ.get("KUBERNETES_NODE_NAME"),
    }
    attributes.update({k: v for k, v in k8s_map.items() if v})
    return Resource.create(attributes)


def _auto_instrument() -> None:
    """Auto-discover and apply installed OTel instrumentors via entry points.

    Supports two modes:
    - Allowlist: Set MITOL_OBSERVABILITY_ALLOW_INSTRUMENTORS to instrument only
      specific instrumentors (recommended for performance-sensitive apps)
    - Skiplist: Set MITOL_OBSERVABILITY_SKIP_INSTRUMENTORS to exclude specific
      instrumentors (default: instrument everything except skipped)
    """
    global _instrumented  # noqa: PLW0603
    if _instrumented:
        log.debug("OpenTelemetry: auto-instrumentation already applied, skipping")
        return
    _instrumented = True

    skip: set[str] = set(
        getattr(settings, "MITOL_OBSERVABILITY_SKIP_INSTRUMENTORS", set())
    )
    allow = getattr(settings, "MITOL_OBSERVABILITY_ALLOW_INSTRUMENTORS", None)
    allow = set(allow) if allow else None

    for ep in importlib.metadata.entry_points(group="opentelemetry_instrumentor"):
        if allow is not None and ep.name not in allow:
            log.debug("Instrumentor not in allowlist: %s", ep.name)
            continue
        if ep.name in skip:
            log.debug("Skipping instrumentor: %s", ep.name)
            continue
        try:
            ep.load()().instrument()
            log.debug("Instrumented: %s", ep.name)
        except Exception:  # noqa: BLE001
            log.warning("Failed to auto-instrument %s", ep.name, exc_info=True)


def configure_opentelemetry() -> TracerProvider | None:
    """Configure OpenTelemetry tracing. Called from AppConfig.ready().

    This function is idempotent — safe to call multiple times (e.g., under
    Django autoreload or in test setups). Subsequent calls return the
    existing tracer provider without re-configuring.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        log.debug("OpenTelemetry: already configured, returning existing provider")
        existing = trace.get_tracer_provider()
        return existing if isinstance(existing, TracerProvider) else None
    _configured = True

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or getattr(
        settings, "OPENTELEMETRY_ENDPOINT", None
    )
    is_debug = getattr(settings, "DEBUG", False)

    if not endpoint and not is_debug:
        log.debug("OpenTelemetry: no endpoint configured and not DEBUG, skipping")
        return None

    log.info("Initializing OpenTelemetry")

    # Register W3C propagators
    set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )

    provider = TracerProvider(resource=_get_resource())
    trace.set_tracer_provider(provider)

    # Console exporter is opt-in even in DEBUG to avoid slowdown during development
    enable_console = getattr(settings, "OPENTELEMETRY_CONSOLE_EXPORTER", False)
    if is_debug and enable_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        log.debug("OpenTelemetry: console exporter added (DEBUG mode)")

    if endpoint:
        try:
            use_grpc = getattr(settings, "OPENTELEMETRY_USE_GRPC", False)
            if use_grpc:
                exporter = GrpcExporter(
                    endpoint=endpoint,
                    insecure=getattr(settings, "OPENTELEMETRY_INSECURE", True),
                )
            else:
                exporter = OTLPSpanExporter(endpoint=endpoint)

            provider.add_span_processor(
                BatchSpanProcessor(
                    exporter,
                    max_export_batch_size=getattr(
                        settings, "OPENTELEMETRY_BATCH_SIZE", 512
                    ),
                    schedule_delay_millis=getattr(
                        settings, "OPENTELEMETRY_SCHEDULE_DELAY_MS", 5000
                    ),
                    export_timeout_millis=getattr(
                        settings, "OPENTELEMETRY_EXPORT_TIMEOUT_MS", 30000
                    ),
                )
            )
            log.info("OpenTelemetry: OTLP exporter configured to %s", endpoint)
        except Exception:  # noqa: BLE001
            log.warning(
                "OpenTelemetry: failed to configure OTLP exporter", exc_info=True
            )

    _auto_instrument()
    log.info("OpenTelemetry initialized successfully")
    return provider


def reset_configuration() -> None:
    """Reset configuration state for testing purposes.

    This allows tests to re-run configure_opentelemetry() with different settings.
    Should only be used in test code.
    """
    global _configured, _instrumented  # noqa: PLW0603
    _configured = False
    _instrumented = False
