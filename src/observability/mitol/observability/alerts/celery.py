"""
Optional Celery-specific alert rules for services that use Celery workers.

Services using Celery should register this group in their alert configuration::

    from mitol.observability.alerts.celery import CeleryAlerts
    AlertRuleGroup.register(CeleryAlerts)

Or simply import this module so that ``CeleryAlerts`` is auto-registered::

    from mitol.observability.alerts import celery as _  # noqa: F401
"""

from __future__ import annotations

import os

from django.conf import settings

from mitol.observability.alerting import AlertRuleGroup, PrometheusRule


def _service_name() -> str:
    return (
        os.environ.get("OTEL_SERVICE_NAME")
        or getattr(settings, "OPENTELEMETRY_SERVICE_NAME", None)
        or "unknown"
    )


class CeleryAlerts(AlertRuleGroup):
    """
    Alert rules for services that run Celery workers.

    Include this group only in services where Celery workers are expected.
    Using the ``(sum(...) or vector(0)) == 0`` pattern ensures the alert fires
    even when all workers have gone down and stopped emitting metrics.
    """

    @classmethod
    def get_prometheus_rules(cls) -> list[PrometheusRule]:
        """Return Celery-specific Prometheus rules parameterized by service name."""
        svc = _service_name()
        return [
            PrometheusRule(
                name=f"{svc}CeleryWorkerDown",
                expr=(f'(sum(celery_worker_up{{service="{svc}"}}) or vector(0)) == 0'),
                for_duration="2m",
                severity="critical",
                annotations={
                    "description": f"No Celery workers are reporting as up for {svc}.",
                    "resolution": "Check Celery worker deployment and broker connectivity.",  # noqa: E501
                },
            ),
        ]
