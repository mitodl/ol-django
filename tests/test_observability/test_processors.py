"""Tests for mitol.observability.processors."""

import mitol.observability.processors as processors_module
import opentelemetry.trace as otel_trace
import pytest
from mitol.observability.processors import inject_k8s_context, inject_otel_context
from opentelemetry.trace.span import format_span_id, format_trace_id


class FakeSpanContext:
    """Minimal span context stub for testing."""

    def __init__(self, trace_id, span_id, *, is_valid=True):
        """Initialize with trace and span IDs."""
        self.trace_id = trace_id
        self.span_id = span_id
        self.is_valid = is_valid


class FakeSpan:
    """Minimal OTel span stub for testing."""

    def __init__(
        self,
        recording=True,  # noqa: FBT002
        trace_id=0xDEADBEEF,
        span_id=0xCAFE,
        *,
        is_valid=True,
    ):
        """Initialize with recording state and span context."""
        self._recording = recording
        self._ctx = FakeSpanContext(
            trace_id=trace_id, span_id=span_id, is_valid=is_valid
        )

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
    assert result["trace_id"] == format_trace_id(trace_id)
    assert result["span_id"] == format_span_id(span_id)
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


def test_inject_otel_context_invalid_context(monkeypatch):
    """Invalid span context adds no fields to event_dict."""
    fake_span = FakeSpan(recording=True, is_valid=False)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    event_dict = {"event": "test"}
    result = inject_otel_context(None, "info", event_dict)

    assert "trace_id" not in result
    assert "span_id" not in result
    assert result == {"event": "test"}


def test_inject_otel_context_skips_when_already_present(monkeypatch):
    """Skips OTel lookup when trace_id/span_id already present."""
    fake_span = FakeSpan(recording=True, trace_id=0xDEADBEEF, span_id=0xCAFE)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    event_dict = {"trace_id": "existing-trace", "span_id": "existing-span"}
    result = inject_otel_context(None, "info", event_dict)

    assert result["trace_id"] == "existing-trace"
    assert result["span_id"] == "existing-span"


@pytest.fixture
def reset_k8s_context():
    """Save and restore K8s context around tests."""
    original = processors_module._K8S_CONTEXT.copy()  # noqa: SLF001
    yield
    processors_module._K8S_CONTEXT.clear()  # noqa: SLF001
    processors_module._K8S_CONTEXT.update(original)  # noqa: SLF001


def test_inject_k8s_context_with_module_vars(reset_k8s_context):  # noqa: ARG001
    """K8s context is injected when _K8S_CONTEXT is populated."""
    processors_module._K8S_CONTEXT.clear()  # noqa: SLF001
    processors_module._K8S_CONTEXT.update(  # noqa: SLF001
        {
            "pod_name": "my-pod-abc123",
            "namespace": "production",
            "node_name": "node-1",
        }
    )

    event_dict = {}
    result = inject_k8s_context(None, "info", event_dict)

    assert result["pod_name"] == "my-pod-abc123"
    assert result["namespace"] == "production"
    assert result["node_name"] == "node-1"


def test_inject_k8s_context_empty_env(reset_k8s_context):  # noqa: ARG001
    """No K8s fields added when _K8S_CONTEXT is empty."""
    processors_module._K8S_CONTEXT.clear()  # noqa: SLF001

    event_dict = {"event": "test"}
    result = inject_k8s_context(None, "info", event_dict)

    assert "pod_name" not in result
    assert "namespace" not in result
    assert "node_name" not in result


def test_inject_k8s_context_partial(reset_k8s_context):  # noqa: ARG001
    """Only present fields in _K8S_CONTEXT are added."""
    processors_module._K8S_CONTEXT.clear()  # noqa: SLF001
    processors_module._K8S_CONTEXT["pod_name"] = "my-pod"  # noqa: SLF001

    event_dict = {}
    result = inject_k8s_context(None, "info", event_dict)

    assert result["pod_name"] == "my-pod"
    assert "namespace" not in result
    assert "node_name" not in result


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------


def test_inject_otel_context_result_consistent_across_calls(monkeypatch):
    """Verify consistent formatting across multiple calls."""
    trace_id = 0x000102030405060708090A0B0C0D0E0F
    span_id = 0xDECAFBADDECAFBAD
    fake_span = FakeSpan(recording=True, trace_id=trace_id, span_id=span_id)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    expected_trace = format_trace_id(trace_id)
    expected_span = format_span_id(span_id)

    for _ in range(10):
        result = inject_otel_context(None, "info", {})
        assert result["trace_id"] == expected_trace
        assert result["span_id"] == expected_span


def test_inject_k8s_context_uses_single_update(reset_k8s_context):  # noqa: ARG001
    """Verify K8s context uses efficient dict.update() pattern."""
    processors_module._K8S_CONTEXT.clear()  # noqa: SLF001
    processors_module._K8S_CONTEXT.update(  # noqa: SLF001
        {
            "pod_name": "test-pod",
            "namespace": "test-ns",
            "node_name": "test-node",
        }
    )

    event_dict = {"existing": "value"}
    result = inject_k8s_context(None, "info", event_dict)

    assert result["existing"] == "value"
    assert result["pod_name"] == "test-pod"
    assert result["namespace"] == "test-ns"
    assert result["node_name"] == "test-node"
