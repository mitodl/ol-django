"""Tests for mitol.observability.processors."""

import mitol.observability.processors as processors_module
import opentelemetry.trace as otel_trace
from mitol.observability.processors import inject_k8s_context, inject_otel_context


class FakeSpanContext:
    """Minimal span context stub for testing."""

    def __init__(self, trace_id, span_id):
        """Initialize with trace and span IDs."""
        self.trace_id = trace_id
        self.span_id = span_id


class FakeSpan:
    """Minimal OTel span stub for testing."""

    def __init__(self, recording=True, trace_id=0xDEADBEEF, span_id=0xCAFE):  # noqa: FBT002
        """Initialize with recording state and span context."""
        self._recording = recording
        self._ctx = FakeSpanContext(trace_id=trace_id, span_id=span_id)

    def is_recording(self):
        """Return whether the span is recording."""
        return self._recording

    def get_span_context(self):
        """Return the span context."""
        return self._ctx


def test_inject_otel_context_with_active_span(monkeypatch):
    """Active recording span adds trace_id and span_id as hex strings."""
    trace_id = 0xDEADBEEFCAFEBABE1234567890ABCDEF
    span_id = 0xBEEFCAFEDEAD1234
    fake_span = FakeSpan(recording=True, trace_id=trace_id, span_id=span_id)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    event_dict = {}
    result = inject_otel_context(None, "info", event_dict)

    assert "trace_id" in result
    assert "span_id" in result
    assert result["trace_id"] == format(trace_id, "032x")
    assert result["span_id"] == format(span_id, "016x")
    assert len(result["trace_id"]) == 32  # noqa: PLR2004
    assert len(result["span_id"]) == 16  # noqa: PLR2004


def test_inject_otel_context_no_active_span(monkeypatch):
    """Non-recording span adds no fields to event_dict."""
    fake_span = FakeSpan(recording=False)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    event_dict = {"event": "test"}
    result = inject_otel_context(None, "info", event_dict)

    assert "trace_id" not in result
    assert "span_id" not in result
    assert result == {"event": "test"}


def test_inject_k8s_context_with_module_vars(monkeypatch):
    """K8s context is injected when module-level variables are set."""
    monkeypatch.setattr(processors_module, "_POD_NAME", "my-pod-abc123")
    monkeypatch.setattr(processors_module, "_NAMESPACE", "production")
    monkeypatch.setattr(processors_module, "_NODE_NAME", "node-1")

    event_dict = {}
    result = inject_k8s_context(None, "info", event_dict)

    assert result["pod_name"] == "my-pod-abc123"
    assert result["namespace"] == "production"
    assert result["node_name"] == "node-1"


def test_inject_k8s_context_empty_env(monkeypatch):
    """No K8s fields added when module variables are None."""
    monkeypatch.setattr(processors_module, "_POD_NAME", None)
    monkeypatch.setattr(processors_module, "_NAMESPACE", None)
    monkeypatch.setattr(processors_module, "_NODE_NAME", None)

    event_dict = {"event": "test"}
    result = inject_k8s_context(None, "info", event_dict)

    assert "pod_name" not in result
    assert "namespace" not in result
    assert "node_name" not in result


def test_inject_k8s_context_partial(monkeypatch):
    """Only present module variables are added."""
    monkeypatch.setattr(processors_module, "_POD_NAME", "my-pod")
    monkeypatch.setattr(processors_module, "_NAMESPACE", None)
    monkeypatch.setattr(processors_module, "_NODE_NAME", None)

    event_dict = {}
    result = inject_k8s_context(None, "info", event_dict)

    assert result["pod_name"] == "my-pod"
    assert "namespace" not in result
    assert "node_name" not in result
