from celery import Celery
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


def get_celery_app() -> Celery:
    """Get the celery app for the project we're running in"""
    app = import_string(settings.MITOL_CELERY_APP_INSTANCE_PATH)

    if not isinstance(app, Celery):
        msg = (
            "Setting MITOL_CELERY_APP_INSTANCE_PATH does not reference "
            "an instance of `celery.Celery`"
        )
        raise ImproperlyConfigured(msg)

    return app
