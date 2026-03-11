"""AppConfig for mitol-django-observability."""

import os

from mitol.common.apps import BaseApp
from mitol.observability.alerts import baseline as _  # noqa: F401
from mitol.observability.logging import configure_structlog
from mitol.observability.telemetry import configure_opentelemetry


class ObservabilityConfig(BaseApp):
    """
    Django AppConfig that wires up OpenTelemetry tracing and structlog logging.

    Add to INSTALLED_APPS:
        "mitol.observability.apps.ObservabilityConfig"

    Configuration is driven by environment variables (see README):
        OTEL_SERVICE_NAME              — service identifier
        OTEL_EXPORTER_OTLP_ENDPOINT   — OTLP collector endpoint
        KUBERNETES_POD_NAME            — injected by Kubernetes Downward API
        KUBERNETES_NAMESPACE           — injected by Kubernetes Downward API
        KUBERNETES_NODE_NAME           — injected by Kubernetes Downward API
        LOG_LEVEL                      — root log level (default: INFO)
        DJANGO_LOG_LEVEL               — django logger level (default: INFO)
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.observability"
    label = "observability"
    verbose_name = "Observability"
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

    # No required_settings — everything degrades gracefully
    required_settings: list[str] = []

    def ready(self) -> None:
        """Initialize observability — configure structlog and OpenTelemetry."""
        configure_structlog()
        configure_opentelemetry()
