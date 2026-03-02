"""OpenTelemetry configuration for Django applications."""

from __future__ import annotations

import importlib.metadata
import logging
import os

from django.conf import settings
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

log = logging.getLogger(__name__)


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
    """Auto-discover and apply installed OTel instrumentors via entry points."""
    skip: set[str] = set(
        getattr(settings, "MITOL_OBSERVABILITY_SKIP_INSTRUMENTORS", set())
    )
    for ep in importlib.metadata.entry_points(group="opentelemetry_instrumentor"):
        if ep.name in skip:
            log.debug("Skipping instrumentor: %s", ep.name)
            continue
        try:
            ep.load()().instrument()
            log.debug("Instrumented: %s", ep.name)
        except Exception:  # noqa: BLE001
            log.warning("Failed to auto-instrument %s", ep.name, exc_info=True)


def configure_opentelemetry() -> TracerProvider | None:
    """Configure OpenTelemetry tracing. Called from AppConfig.ready()."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or getattr(
        settings, "OPENTELEMETRY_ENDPOINT", None
    )
    is_debug = getattr(settings, "DEBUG", False)

    if not endpoint and not is_debug:
        log.debug("OpenTelemetry: no endpoint configured and not DEBUG, skipping")
        return None

    log.info("Initializing OpenTelemetry")

    # Register W3C propagators
    from opentelemetry.baggage.propagation import W3CBaggagePropagator

    set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )

    provider = TracerProvider(resource=_get_resource())
    trace.set_tracer_provider(provider)

    if is_debug:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        log.debug("OpenTelemetry: console exporter added (DEBUG mode)")

    if endpoint:
        try:
            use_grpc = getattr(settings, "OPENTELEMETRY_USE_GRPC", False)
            if use_grpc:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter as GrpcExporter,
                )

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
                        settings, "OPENTELEMETRY_EXPORT_TIMEOUT_MS", 5000
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
