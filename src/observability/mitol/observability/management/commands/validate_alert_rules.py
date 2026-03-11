"""Management command to validate alert rule definitions."""

import re
import sys

from django.core.management.base import BaseCommand

from mitol.observability.alerting import LokiRule, PrometheusRule, get_all_rule_groups
from mitol.observability.alerts.baseline import BaselineAlerts

_DURATION_RE = re.compile(r"^\d+[smh]$")


def _validate_prometheus_expr(rule: PrometheusRule, errors: list[str]) -> None:
    """Check that a PromQL expression has balanced parentheses."""
    depth = 0
    for ch in rule.expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            break
    if depth != 0:
        errors.append(f"PrometheusRule '{rule.name}': expr has unbalanced parentheses")


def _validate_rule(rule: LokiRule | PrometheusRule, errors: list[str]) -> None:
    """Validate a single rule, appending error messages to the list."""
    rule_type = type(rule).__name__

    if not _DURATION_RE.match(rule.for_duration):
        errors.append(
            f"{rule_type} '{rule.name}': for_duration '{rule.for_duration}'"
            " must match \\d+[smh]"
        )

    if isinstance(rule, LokiRule):
        if "{" not in rule.expr or "}" not in rule.expr:
            errors.append(
                f"LokiRule '{rule.name}': expr must contain a label selector ({{...}})"
            )
    elif isinstance(rule, PrometheusRule):
        _validate_prometheus_expr(rule, errors)

    if rule.severity == "critical":
        errors.extend(
            f"{rule_type} '{rule.name}' (severity=critical): missing '{a}' annotation"
            for a in ("description", "resolution")
            if a not in rule.annotations
        )


class Command(BaseCommand):
    """Validate all registered alert rule definitions, exit 1 on failure."""

    help = "Validate all registered alert rule definitions"

    def handle(self, *args, **options):  # noqa: ARG002
        """Execute the command — validate all alert rules."""
        errors: list[str] = []

        for group in get_all_rule_groups():
            if group is BaselineAlerts:
                continue
            for rule in group.get_loki_rules() + group.get_prometheus_rules():
                _validate_rule(rule, errors)

        for rule in (
            BaselineAlerts.get_loki_rules() + BaselineAlerts.get_prometheus_rules()
        ):
            _validate_rule(rule, errors)

        if errors:
            self.stderr.write("Alert rule validation failed:")
            for error in errors:
                self.stderr.write(f"  - {error}")
            sys.exit(1)

        self.stdout.write("All alert rules valid.")
