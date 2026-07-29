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

## Postgres integration

To emit OTel spans for database queries, install the `postgres` extra:

```
pip install "mitol-django-observability[postgres]"
```

This adds two things:

- `opentelemetry-instrumentation-psycopg`, auto-discovered via the `opentelemetry_instrumentor` entry-point group — no extra configuration required.
- `psycopg[c]`, the compiled binding, which is the implementation you want in production. The section below explains why the extra decides this on your behalf.

### Build prerequisites

`psycopg[c]` is compiled from source at install time, so the build environment needs a C compiler, Python development headers, `libpq-dev`, and `pg_config` on `PATH`. Images built on `mitodl/ol-python-base` already provide all four.

CI runners generally do not. GitHub's `ubuntu-24.04` image, for instance, ships PostgreSQL but not `libpq-dev`, so add it to your `Aptfile` (or equivalent) alongside the other `-dev` packages:

```
libpq-dev
```

If you are in an environment that genuinely cannot compile, install `psycopg[binary]` explicitly in your application — a pre-compiled wheel that bundles its own `libpq` and `libssl`. Those bundled libraries do not receive OS security updates, which is why it is not the default here.

### Why the extra decides the driver

The psycopg instrumentation targets **psycopg 3**, so installing this extra puts psycopg 3 in your environment. That has a consequence which is easy to miss: it changes which driver Django uses. Django's Postgres backend prefers psycopg 3 over psycopg2 whenever psycopg 3 is importable ([`django/db/backends/postgresql/base.py`](https://github.com/django/django/blob/5.2.15/django/db/backends/postgresql/base.py#L24-L30)):

```python
try:
    try:
        import psycopg as Database
    except ImportError:
        import psycopg2 as Database
```

An application running on psycopg2 therefore switches to psycopg 3 the moment this instrumentation is installed, with no change to its own code and nothing in its dependency diff that names a driver.

Since the extra is already making that decision, it specifies the implementation too. psycopg 3 ships three interchangeable bindings to libpq, and a bare `psycopg` dependency selects the slowest:

| dependency | binding | notes |
| --- | --- | --- |
| `psycopg` | pure Python, via `ctypes` | upstream calls it "much slower"; intended for local development and small tasks |
| `psycopg[c]` | compiled, linked against the system libpq | psycopg's recommendation for production — system `libpq`/`libssl` upgrades carry through |
| `psycopg[binary]` | compiled, bundles its own libpq/libssl | no build tools needed, but the bundled libraries do not receive OS security updates |

Extras union across dependency resolution, so requesting `psycopg[c]` here installs the compiled binding regardless of how the application declares psycopg itself.

Check what a deployed process actually resolved to — psycopg selects the best available implementation at import, so this reflects what is installed rather than what was requested:

```python
>>> import psycopg
>>> psycopg.pq.__impl__
'c'
```

See psycopg's [installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html#install-grid) and [`pq` module implementations](https://www.psycopg.org/psycopg3/docs/api/pq.html#pq-impl) for the full comparison.
