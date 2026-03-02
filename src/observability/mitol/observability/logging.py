"""Structlog configuration for Django applications."""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

import structlog

from mitol.observability.processors import inject_k8s_context, inject_otel_context


def _get_log_level() -> str:
    return os.environ.get("LOG_LEVEL", "INFO").upper()


def _get_django_log_level() -> str:
    return os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()


def _shared_processors() -> list[Any]:
    """Processors used in both dev and prod chains."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        inject_otel_context,
        inject_k8s_context,
        structlog.processors.StackInfoRenderer(),
    ]


def configure_structlog(debug: bool | None = None) -> None:
    """
    Configure structlog and route stdlib logging through it.

    Args:
        debug: Override debug mode detection. If None, reads from Django settings.
    """
    from django.conf import settings

    if debug is None:
        debug = getattr(settings, "DEBUG", False)

    log_level = _get_log_level()
    django_log_level = _get_django_log_level()

    shared = _shared_processors()

    if debug:
        processors = [
            *shared,
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            *shared,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog's ProcessorFormatter
    # so that third-party libraries (django, celery, etc.) emit structured records
    stdlib_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        inject_otel_context,
        inject_k8s_context,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=stdlib_processors,
        foreign_pre_chain=shared,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "()": lambda: handler,
                }
            },
            "loggers": {
                "django": {
                    "handlers": ["console"],
                    "level": django_log_level,
                    "propagate": False,
                },
                "django.request": {
                    "handlers": ["console"],
                    "level": django_log_level,
                    "propagate": False,
                },
                "boto3": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "botocore": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "opensearch": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "nplusone": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "zeal": {"handlers": ["console"], "level": "ERROR", "propagate": False},
            },
            "root": {"handlers": ["console"], "level": log_level},
        }
    )
