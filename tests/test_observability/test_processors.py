"""Tests for mitol.observability.processors."""

import mitol.observability.processors as processors_module
import opentelemetry.trace as otel_trace
import pytest
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


# ---------------------------------------------------------------------------
# Performance / caching tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_format_cache():
    """Clear the _format_span_ids LRU cache before each test."""
    processors_module._format_span_ids.cache_clear()  # noqa: SLF001
    yield
    processors_module._format_span_ids.cache_clear()  # noqa: SLF001


def test_format_span_ids_cached_on_repeat_calls(monkeypatch):
    """_format_span_ids returns cached strings for the same (trace_id, span_id)."""
    trace_id = 0xDEADBEEFCAFEBABE1234567890ABCDEF
    span_id = 0xBEEFCAFEDEAD1234
    fake_span = FakeSpan(recording=True, trace_id=trace_id, span_id=span_id)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    n_calls = 50
    for _ in range(n_calls):
        inject_otel_context(None, "info", {})

    info = processors_module._format_span_ids.cache_info()  # noqa: SLF001
    assert info.misses == 1, "first call should be a cache miss"
    assert info.hits == n_calls - 1, "subsequent calls should all be cache hits"


def test_format_span_ids_distinct_spans_are_separate_entries(monkeypatch):
    """Each unique (trace_id, span_id) pair gets its own cache entry."""
    spans = [
        FakeSpan(recording=True, trace_id=0xAAAA0000, span_id=0x0001),
        FakeSpan(recording=True, trace_id=0xBBBB0000, span_id=0x0002),
        FakeSpan(recording=True, trace_id=0xCCCC0000, span_id=0x0003),
    ]

    for span in spans:
        monkeypatch.setattr(otel_trace, "get_current_span", lambda s=span: s)
        inject_otel_context(None, "info", {})

    info = processors_module._format_span_ids.cache_info()  # noqa: SLF001
    assert info.misses == len(spans), "each distinct span should be a separate miss"
    assert info.currsize == len(spans)


def test_inject_otel_context_result_consistent_with_cache(monkeypatch):
    """Cached values match the directly-formatted expected strings."""
    trace_id = 0x000102030405060708090A0B0C0D0E0F
    span_id = 0xDECAFBADDECAFBAD
    fake_span = FakeSpan(recording=True, trace_id=trace_id, span_id=span_id)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    # Two calls: one miss (cold), one hit (warm) — both must return correct values.
    for _ in range(2):
        result = inject_otel_context(None, "info", {})
        assert result["trace_id"] == format(trace_id, "032x")
        assert result["span_id"] == format(span_id, "016x")


def test_inject_otel_context_no_span_does_not_populate_cache(monkeypatch):
    """When no span is recording, _format_span_ids is never called."""
    fake_span = FakeSpan(recording=False)

    monkeypatch.setattr(otel_trace, "get_current_span", lambda: fake_span)

    for _ in range(10):
        inject_otel_context(None, "info", {})

    info = processors_module._format_span_ids.cache_info()  # noqa: SLF001
    assert info.misses == 0
    assert info.hits == 0
