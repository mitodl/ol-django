"""Custom structlog processors for observability context injection."""

import os
from typing import Any

from opentelemetry import trace
from opentelemetry.trace.span import format_span_id, format_trace_id

# Precompute K8s context dict at import time — values don't change during process
# lifetime. Using a single dict.update() is faster than multiple conditional writes.
_K8S_CONTEXT: dict[str, str] = {
    k: v
    for k, v in {
        "pod_name": os.environ.get("KUBERNETES_POD_NAME"),
        "namespace": os.environ.get("KUBERNETES_NAMESPACE"),
        "node_name": os.environ.get("KUBERNETES_NODE_NAME"),
    }.items()
    if v
}


def inject_otel_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace context into structlog event dict.

    Performance notes:
    - Skips work if trace_id/span_id already present (e.g., bound via contextvars)
    - Uses OTel's built-in formatters (no lru_cache lock overhead)
    - Checks is_valid before is_recording for faster invalid-context fast-path
    """
    if "trace_id" in event_dict and "span_id" in event_dict:
        return event_dict

    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return event_dict

    if not span.is_recording():
        return event_dict

    event_dict["trace_id"] = format_trace_id(ctx.trace_id)
    event_dict["span_id"] = format_span_id(ctx.span_id)
    return event_dict


def inject_k8s_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject Kubernetes metadata into structlog event dict.

    Performance notes:
    - Uses precomputed dict with single update() call
    - Fast-path skip when no K8s env vars are set
    """
    if _K8S_CONTEXT:
        event_dict.update(_K8S_CONTEXT)
    return event_dict
