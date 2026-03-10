"""Tests for generate_alert_rules and validate_alert_rules management commands."""

import pytest
import yaml
from django.core.management import call_command
from mitol.observability.alerting import (
    AlertRuleGroup,
    LokiRule,
    PrometheusRule,
    _registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Remove test-only rule groups from the registry after each test."""
    before = dict(_registry)
    yield
    _registry.clear()
    _registry.update(before)


def test_generate_alert_rules_loki(tmp_path, monkeypatch):
    """generate_alert_rules --format=loki writes valid YAML with correct structure."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

    call_command("generate_alert_rules", format="loki", output_dir=str(tmp_path))

    out_file = tmp_path / "test-svc-loki.yaml"
    assert out_file.exists()

    doc = yaml.safe_load(out_file.read_text())
    assert "namespace" in doc
    assert "groups" in doc
    assert isinstance(doc["groups"], list)
    assert len(doc["groups"]) > 0
    group = doc["groups"][0]
    assert "rules" in group
    assert len(group["rules"]) > 0
    # Each rule must have required keys
    for rule in group["rules"]:
        assert "alert" in rule
        assert "expr" in rule
        assert "for" in rule
        assert "labels" in rule


def test_generate_alert_rules_cortex(tmp_path, monkeypatch):
    """generate_alert_rules --format=cortex writes valid YAML with correct structure."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

    call_command("generate_alert_rules", format="cortex", output_dir=str(tmp_path))

    out_file = tmp_path / "test-svc-cortex.yaml"
    assert out_file.exists()

    doc = yaml.safe_load(out_file.read_text())
    assert "namespace" in doc
    assert "groups" in doc


def test_generate_alert_rules_both(tmp_path, monkeypatch):
    """generate_alert_rules --format=both writes both files."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

    call_command("generate_alert_rules", format="both", output_dir=str(tmp_path))

    assert (tmp_path / "test-svc-loki.yaml").exists()
    assert (tmp_path / "test-svc-cortex.yaml").exists()


def test_validate_alert_rules_valid(monkeypatch):
    """validate_alert_rules exits normally when all rules are valid."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")

    # Should not raise SystemExit
    call_command("validate_alert_rules")


def test_validate_alert_rules_missing_resolution():
    """Command exits 1 when a critical rule lacks the 'resolution' annotation."""

    class BadAlerts(AlertRuleGroup):
        bad_rule = PrometheusRule(
            name="MissingResolution",
            expr="sum(rate(errors[5m])) > 0",
            for_duration="5m",
            severity="critical",
            annotations={"description": "something is wrong"},
            # missing "resolution"
        )

    with pytest.raises(SystemExit) as exc_info:
        call_command("validate_alert_rules")

    assert exc_info.value.code == 1


def test_validate_alert_rules_invalid_duration():
    """validate_alert_rules exits with code 1 for invalid for_duration."""

    class BadDurationAlerts(AlertRuleGroup):
        bad_rule = LokiRule(
            name="BadDuration",
            expr='{service="svc"} |json',
            for_duration="5minutes",  # invalid — should be 5m
            severity="info",
        )

    with pytest.raises(SystemExit) as exc_info:
        call_command("validate_alert_rules")

    assert exc_info.value.code == 1
