"""
Built-in baseline alert rules automatically applied to every service.

These provide minimum viable alerting coverage with zero application code.
Rules are parameterized by OTEL_SERVICE_NAME.
"""

from __future__ import annotations

import os

from django.conf import settings
from mitol.observability.alerting import AlertRuleGroup, LokiRule, PrometheusRule


def _service_name() -> str:
    return (
        os.environ.get("OTEL_SERVICE_NAME")
        or getattr(settings, "OPENTELEMETRY_SERVICE_NAME", None)
        or "unknown"
    )


def _error_rate_threshold() -> float:
    return float(
        getattr(settings, "MITOL_OBSERVABILITY_ALERT_ERROR_RATE_THRESHOLD", 0.01)
    )


def _latency_p99_threshold() -> float:
    return float(
        getattr(settings, "MITOL_OBSERVABILITY_ALERT_LATENCY_P99_THRESHOLD", 2.0)
    )


class BaselineAlerts(AlertRuleGroup):
    """Baseline alert rules included for every service that uses this plugin."""

    @classmethod
    def get_prometheus_rules(cls) -> list[PrometheusRule]:
        """Return baseline Prometheus rules parameterized by service name."""
        svc = _service_name()
        error_threshold = _error_rate_threshold()
        latency_threshold = _latency_p99_threshold()
        return [
            PrometheusRule(
                name=f"{svc}HighErrorRate",
                expr=(
                    f'sum(rate(http_server_duration_milliseconds_count{{service="{svc}",http_status_code=~"5.."}}[5m])) / '  # noqa: E501
                    f'sum(rate(http_server_duration_milliseconds_count{{service="{svc}"}}[5m])) > {error_threshold}'  # noqa: E501
                ),
                for_duration="5m",
                severity="critical",
                annotations={
                    "description": f"{svc} is returning HTTP 5xx errors at an elevated rate (>{error_threshold * 100:.0f}%).",  # noqa: E501
                    "resolution": "Check application logs and recent deployments.",
                },
            ),
            PrometheusRule(
                name=f"{svc}HighLatencyP99",
                expr=(
                    f'histogram_quantile(0.99, sum(rate(http_server_duration_milliseconds_bucket{{service="{svc}"}}[10m])) by (le)) > {latency_threshold * 1000}'  # noqa: E501
                ),
                for_duration="10m",
                severity="warning",
                annotations={
                    "description": f"{svc} P99 request latency exceeds {latency_threshold}s.",  # noqa: E501
                    "resolution": "Investigate slow queries, downstream dependencies, or resource contention.",  # noqa: E501
                },
            ),
        ]

    @classmethod
    def get_loki_rules(cls) -> list[LokiRule]:
        """Return baseline Loki rules parameterized by service name."""
        svc = _service_name()
        return [
            LokiRule(
                name=f"{svc}ErrorLogSpike",
                expr=f'sum(rate({{service="{svc}"}} |json | level="error" [5m])) > 0.5',
                for_duration="5m",
                severity="warning",
                annotations={
                    "description": f"{svc} is emitting error-level log records at an elevated rate.",  # noqa: E501
                    "resolution": "Check Loki for recent error patterns.",
                },
            ),
            LokiRule(
                name=f"{svc}ExceptionLogSpike",
                expr=f'sum(rate({{service="{svc}"}} |json |= "exception" [5m])) > 0.1',
                for_duration="2m",
                severity="critical",
                annotations={
                    "description": f"{svc} is logging unhandled exceptions at an elevated rate.",  # noqa: E501
                    "resolution": "Check Loki for traceback details and Tempo for associated traces.",  # noqa: E501
                },
            ),
        ]
