# mitol-django-observability

MIT Open Learning Django plugin for OpenTelemetry tracing, structured logging (structlog), and alerting-as-code.

## Installation

Add to `INSTALLED_APPS`:
```python
"mitol.observability.apps.ObservabilityConfig",
```

See the [RFC](https://github.com/mitodl/hq/discussions/10361) for full documentation.

## Celery integration

To propagate structured log context (request ID, user ID, …) from web workers into Celery tasks and ensure Celery workers emit JSON logs through the same structlog pipeline, install the `celery` extra and follow the steps below.

### 1. Install the extra

```
pip install "mitol-django-observability[celery]"
```

This adds `django-structlog[celery]` (context propagation) and `opentelemetry-instrumentation-celery` (OTel task spans, auto-discovered).

### 2. Django settings

```python
MIDDLEWARE = [
    # …
    "django_structlog.middlewares.RequestMiddleware",
]

DJANGO_STRUCTLOG_CELERY_ENABLED = True
```

### 3. Celery application

```python
from celery import Celery
from celery.signals import setup_logging
from django_structlog.celery.steps import DjangoStructLogInitStep

from mitol.observability.celery import setup_celery_logging

app = Celery("yourproject")

@setup_logging.connect
def on_setup_logging(**kwargs):
    # Prevent Celery from overriding structlog's logging config in workers.
    setup_celery_logging(**kwargs)

# Propagate web-request context into task execution.
app.steps["worker"].add(DjangoStructLogInitStep)
```

### How it works

- `setup_celery_logging` calls `configure_structlog(force=True)`, re-applying the structlog pipeline after Celery resets logging during worker boot.
- `DjangoStructLogInitStep` installs signal handlers that bind the request context (captured by `RequestMiddleware`) to the structlog context vars before each task runs and clears it after.
- `opentelemetry-instrumentation-celery` is auto-discovered via the `opentelemetry_instrumentor` entry-point group — no extra configuration required.
