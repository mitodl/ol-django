"""Custom structlog processors for observability context injection."""

import os
from typing import Any

from opentelemetry import trace

# Cache K8s values at import time — they don't change during process lifetime
_POD_NAME: str | None = os.environ.get("KUBERNETES_POD_NAME")
_NAMESPACE: str | None = os.environ.get("KUBERNETES_NAMESPACE")
_NODE_NAME: str | None = os.environ.get("KUBERNETES_NODE_NAME")


def inject_otel_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace context into structlog event dict."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def inject_k8s_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject Kubernetes metadata into structlog event dict."""
    if _POD_NAME:
        event_dict["pod_name"] = _POD_NAME
    if _NAMESPACE:
        event_dict["namespace"] = _NAMESPACE
    if _NODE_NAME:
        event_dict["node_name"] = _NODE_NAME
    return event_dict
