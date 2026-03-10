"""Alert rule definition framework for Django applications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Global registry of all AlertRuleGroup subclasses, keyed by fully-qualified name
# to deduplicate on module reload (common in tests and Django dev server)
_registry: dict[str, type[AlertRuleGroup]] = {}


@dataclass
class LokiRule:
    """A Loki (LogQL) alerting rule."""

    name: str
    expr: str
    for_duration: str
    severity: str  # "critical" | "warning" | "info"
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_cortex_dict(self) -> dict[str, Any]:
        """Serialize to Cortex/Loki alert rule dict format."""
        return {
            "alert": self.name,
            "expr": self.expr,
            "for": self.for_duration,
            "labels": {"severity": self.severity, **self.labels},
            "annotations": self.annotations,
        }


@dataclass
class PrometheusRule:
    """A Prometheus (PromQL) alerting rule."""

    name: str
    expr: str
    for_duration: str
    severity: str  # "critical" | "warning" | "info"
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_cortex_dict(self) -> dict[str, Any]:
        """Serialize to Cortex/Prometheus alert rule dict format."""
        return {
            "alert": self.name,
            "expr": self.expr,
            "for": self.for_duration,
            "labels": {"severity": self.severity, **self.labels},
            "annotations": self.annotations,
        }


class AlertRuleGroup:
    """
    Base class for defining a group of alert rules colocated with application code.

    Subclasses are automatically registered and discovered by management commands.

    Usage:
        class MyAppAlerts(AlertRuleGroup):
            service = "my-app"
            namespace = "my-app-alerts"

            high_error_rate = PrometheusRule(
                name="MyAppHighErrorRate",
                expr=(
                    'sum(rate(http_server_duration_count'
                    '{service="my-app",status=~"5.."}[5m])) > 0.01'
                ),
                for_duration="5m",
                severity="critical",
                annotations={"description": "...", "resolution": "..."},
            )
    """

    service: str = "unknown"
    namespace: str = "app-alerts"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register subclasses in the global rule group registry."""
        super().__init_subclass__(**kwargs)
        key = f"{cls.__module__}.{cls.__qualname__}"
        _registry[key] = cls

    @classmethod
    def get_loki_rules(cls) -> list[LokiRule]:
        """Return all LokiRule instances defined on this class."""
        return [v for v in vars(cls).values() if isinstance(v, LokiRule)]

    @classmethod
    def get_prometheus_rules(cls) -> list[PrometheusRule]:
        """Return all PrometheusRule instances defined on this class."""
        return [v for v in vars(cls).values() if isinstance(v, PrometheusRule)]


def get_all_rule_groups() -> list[type[AlertRuleGroup]]:
    """Return all registered AlertRuleGroup subclasses."""
    return list(_registry.values())
