"""
Importable settings module for structlog-based logging.

Usage in Django settings:
    from mitol.common.envs import import_settings_modules
    import_settings_modules("mitol.observability.settings.logging")

This replaces the LOGGING dict. Applications should remove any existing
LOGGING dict from their settings when using this module.
"""

import os

import structlog

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
DJANGO_LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()


def _make_formatter():
    """
    Create a ProcessorFormatter whose renderer is chosen from Django settings.

    This factory is called by Django's logging configuration machinery *after*
    settings are fully loaded, so ``settings.DEBUG`` is always available and
    we avoid the boot-time mismatch that arises when reading the ``DEBUG``
    environment variable at module import time.
    """
    try:
        from django.conf import settings  # noqa: PLC0415

        debug = getattr(settings, "DEBUG", False)
    except Exception:  # noqa: BLE001
        debug = False

    from mitol.observability.logging import (  # noqa: PLC0415
        _EXCEPTION_RENDERER,
        _shared_processors,
    )

    if debug:
        # ConsoleRenderer handles exc_info natively; no extra processor needed.
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
        processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ]
    else:
        # _EXCEPTION_RENDERER must appear before JSONRenderer so that the
        # exc_info field from foreign stdlib records (Django, third-party
        # libraries) is converted to a structured ``exception`` dict instead
        # of being serialised as a raw Python traceback object reference.
        renderer = structlog.processors.JSONRenderer()
        processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _EXCEPTION_RENDERER,
            renderer,
        ]

    return structlog.stdlib.ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=_shared_processors(),
    )


# structlog ProcessorFormatter-based LOGGING dict.
# Actual structlog configuration happens in apps.py via configure_structlog().
# This dict only sets up the stdlib logging side so that Django and third-party
# libraries emit through the same structlog pipeline.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structlog": {
            "()": _make_formatter,
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structlog",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        "boto3": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "botocore": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "opensearch": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "nplusone": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "zeal": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        # Celery worker and task loggers
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "celery.task": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "celery.worker": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # django-structlog context propagation middleware
        "django_structlog": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
