"""
Celery integration helpers for mitol-django-observability.

This module provides a ``setup_celery_logging`` function that re-applies the
structlog configuration inside Celery worker processes.  Celery fires a
``setup_logging`` signal during worker boot, giving applications the
opportunity to override its default logging setup.  Without a receiver,
Celery installs its own basic logging config; with one, it defers to the
application entirely.

Usage
-----
In your ``celery.py`` (or wherever you create your Celery application)::

    from celery import Celery
    from celery.signals import setup_logging
    from django_structlog.celery.steps import DjangoStructLogInitStep

    from mitol.observability.celery import setup_celery_logging

    app = Celery("yourproject")

    # Let structlog handle all worker logging; prevents Celery's default
    # formatter from clobbering the JSON/console output we configure.
    @setup_logging.connect
    def on_setup_logging(**kwargs):
        setup_celery_logging(**kwargs)

    # Propagate the web-request structlog context (request_id, user_id, …)
    # into Celery tasks via django-structlog's worker step.
    app.steps["worker"].add(DjangoStructLogInitStep)

You also need the following in your Django settings::

    DJANGO_STRUCTLOG_CELERY_ENABLED = True

And ``django_structlog.middlewares.RequestMiddleware`` in MIDDLEWARE so that
the web-request context is available to bind to tasks.

OpenTelemetry
-------------
Celery spans are traced automatically when ``opentelemetry-instrumentation-celery``
is installed.  The observability app's auto-instrumentation discovers it via
the ``opentelemetry_instrumentor`` entry-point group — no extra configuration
required beyond installing the package::

    pip install "mitol-django-observability[celery]"
"""

from __future__ import annotations


def setup_celery_logging(**_kwargs) -> None:
    """
    Configure structlog in a Celery worker process.

    Call this from your ``@setup_logging.connect`` receiver.  It forces
    structlog to re-apply its configuration even if ``AppConfig.ready()``
    already ran earlier in the process lifetime, because Celery can reset the
    logging configuration between Django setup and the ``setup_logging`` signal.

    Args:
        **kwargs: Celery passes ``loglevel``, ``logfile``, ``format``, and
            ``colorize`` here; they are accepted but ignored — log level and
            debug mode are read from the ``LOG_LEVEL`` env var and
            ``settings.DEBUG`` respectively, matching the web-process behaviour.
    """
    from mitol.observability.logging import configure_structlog  # noqa: PLC0415

    configure_structlog(force=True)
