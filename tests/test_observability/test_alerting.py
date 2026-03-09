"""Tests for mitol.observability.alerting and baseline rules."""

import pytest
from django.test import override_settings
from mitol.observability.alerting import (
    AlertRuleGroup,
    LokiRule,
    PrometheusRule,
    _registry,
    get_all_rule_groups,
)
from mitol.observability.alerts.baseline import BaselineAlerts


@pytest.fixture(autouse=True)
def clean_registry():
    """Remove test-only rule groups from the registry after each test."""
    before = set(_registry)
    yield
    _registry[:] = [g for g in _registry if g in before]


def test_rule_group_registration():
    """Defining an AlertRuleGroup subclass registers it automatically."""

    class TestAlerts(AlertRuleGroup):
        service = "test-svc"
        high_error = PrometheusRule(
            name="TestHighError",
            expr="sum(rate(errors[5m])) > 0.01",
            for_duration="5m",
            severity="critical",
            annotations={"description": "desc", "resolution": "fix it"},
        )

    groups = get_all_rule_groups()
    assert TestAlerts in groups


def test_loki_rule_to_cortex_dict():
    """LokiRule.to_cortex_dict() returns the expected schema."""
    rule = LokiRule(
        name="TestLokiAlert",
        expr='{service="test"} |json | level="error"',
        for_duration="5m",
        severity="warning",
        annotations={"description": "too many errors"},
    )
    d = rule.to_cortex_dict()

    assert d["alert"] == "TestLokiAlert"
    assert d["expr"] == '{service="test"} |json | level="error"'
    assert d["for"] == "5m"
    assert d["labels"]["severity"] == "warning"
    assert d["annotations"]["description"] == "too many errors"


def test_prometheus_rule_to_cortex_dict():
    """PrometheusRule.to_cortex_dict() returns the expected schema."""
    rule = PrometheusRule(
        name="TestPromAlert",
        expr="sum(rate(http_errors[5m])) > 0.1",
        for_duration="10m",
        severity="critical",
        labels={"team": "platform"},
        annotations={"description": "high error rate", "resolution": "check logs"},
    )
    d = rule.to_cortex_dict()

    assert d["alert"] == "TestPromAlert"
    assert d["for"] == "10m"
    assert d["labels"]["severity"] == "critical"
    assert d["labels"]["team"] == "platform"
    assert d["annotations"]["description"] == "high error rate"
    assert d["annotations"]["resolution"] == "check logs"


def test_get_loki_rules_from_group():
    """get_loki_rules() returns only LokiRule class attributes."""

    class MixedAlerts(AlertRuleGroup):
        loki_rule = LokiRule(
            name="LokiOne",
            expr='{service="svc"} |json',
            for_duration="1m",
            severity="info",
        )
        prom_rule = PrometheusRule(
            name="PromOne",
            expr="up == 0",
            for_duration="1m",
            severity="warning",
        )

    loki = MixedAlerts.get_loki_rules()
    prom = MixedAlerts.get_prometheus_rules()

    assert len(loki) == 1
    assert loki[0].name == "LokiOne"
    assert len(prom) == 1
    assert prom[0].name == "PromOne"


@override_settings(OPENTELEMETRY_SERVICE_NAME="test-baseline-svc")
def test_baseline_returns_rules(monkeypatch):
    """BaselineAlerts returns the expected number of rules."""
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

    prom_rules = BaselineAlerts.get_prometheus_rules()
    loki_rules = BaselineAlerts.get_loki_rules()

    assert len(prom_rules) == 3  # noqa: PLR2004
    assert len(loki_rules) == 2  # noqa: PLR2004


def test_baseline_uses_service_name(monkeypatch):
    """BaselineAlerts rule names contain the configured service name."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

    for rule in BaselineAlerts.get_prometheus_rules() + BaselineAlerts.get_loki_rules():
        assert "test-svc" in rule.name, (
            f"Rule '{rule.name}' doesn't contain service name"
        )
