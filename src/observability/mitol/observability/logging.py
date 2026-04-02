"""Structlog configuration for Django applications."""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

import structlog
from django.conf import settings
from mitol.observability.processors import inject_k8s_context, inject_otel_context

# Idempotency guard prevents double-configuration under Django autoreload
_configured = False


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


def configure_structlog(*, debug: bool | None = None) -> None:
    """
    Configure structlog and route stdlib logging through it.

    This function is idempotent — safe to call multiple times (e.g., under
    Django autoreload or in test setups).

    Args:
        debug: Override debug mode detection. If None, reads from Django settings.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return
    _configured = True

    if debug is None:
        debug = getattr(settings, "DEBUG", False)

    log_level = _get_log_level()
    django_log_level = _get_django_log_level()

    shared = _shared_processors()

    if debug:
        exc_processor = structlog.dev.set_exc_info
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        exc_processor = structlog.processors.format_exc_info
        renderer = structlog.processors.JSONRenderer()

    # structlog pipeline: ends with wrap_for_formatter so that stdlib records
    # routed through ProcessorFormatter share the same pre-chain processing.
    structlog.configure(
        processors=[
            *shared,
            exc_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter handles both structlog records (wrapped above) and
    # foreign stdlib records (via foreign_pre_chain).  The final processor
    # must be a renderer that returns a string.
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
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


def reset_configuration() -> None:
    """Reset configuration state for testing purposes.

    This allows tests to re-run configure_structlog() with different settings.
    Should only be used in test code.
    """
    global _configured  # noqa: PLW0603
    _configured = False
