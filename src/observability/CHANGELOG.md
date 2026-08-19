
<a id='changelog-2026.8.19'></a>
## [2026.8.19] - 2026-08-19

### Removed

- Removed support for Python 3.10

### Added

- Added `celery`, `celery.task`, `celery.worker`, and `django_structlog` loggers to the stdlib logging configuration in both `configure_structlog()` and `settings/logging.py`, so Celery worker output and `django-structlog` context propagation logs are routed through the structlog formatter.
- Added `force` parameter to `configure_structlog()` to support Celery worker processes where logging must be re-applied after Celery resets the logging configuration.

- Added a `postgres` extra providing `opentelemetry-instrumentation-psycopg` and `psycopg[c]`, the instrumentation being auto-discovered via the `opentelemetry_instrumentor` entry-point group.
- Documented in the README why the extra decides the database driver: the instrumentation targets psycopg 3, and Django's Postgres backend prefers psycopg 3 over psycopg2 whenever it is importable, so installing it switches an application's driver with nothing in the dependency diff naming one. Since the extra already makes that decision, it pins the compiled binding rather than leaving a bare `psycopg` to resolve to the pure-Python `ctypes` implementation that upstream documents as "much slower".
- Documented the resulting build prerequisites (C compiler, Python headers, `libpq-dev`, `pg_config` — all present in `ol-python-base`, absent from GitHub's `ubuntu-24.04` runners) and `psycopg[binary]` as the escape hatch for environments that cannot compile.

- Added a `MeterProvider`, so instrumentation emits unsampled RED metrics. Nothing here defines a metric: installing a global provider is enough for `DjangoInstrumentor` to build `http.server.duration` and `http.server.active_requests`, which then cover every request rather than the fraction of traces that survive sampling. Previously the only RED signal was Grafana Cloud's `traces_spanmetrics_*`, derived from ingested traces — and because the tail sampler keeps all errors and everything slow on top of a probabilistic baseline, those over-represent both by construction.
- Metrics are configured from the environment only, and stay off until `OTEL_EXPORTER_OTLP_ENDPOINT` (a base URL) or `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` is set. `OPENTELEMETRY_ENDPOINT` is deliberately not reused: it is a full traces URL ending in `/v1/traces`, so borrowing it would POST metrics to the traces path. `OTEL_METRIC_EXPORT_INTERVAL` now means something — `PeriodicExportingMetricReader` reads it.
- Fixed the early-return in `configure_opentelemetry()` skipping metrics setup when only `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` was configured. The guard keyed off the traces endpoint alone, so a metrics-only configuration returned before `_configure_metrics` ever ran.
- Metrics now follow `OPENTELEMETRY_USE_GRPC` like tracing does. Sharing `OTEL_EXPORTER_OTLP_ENDPOINT` between signals meant an HTTP metric exporter would POST `/v1/metrics` at a gRPC-only port and deliver nothing.
- Metric exporter and reader construction is wrapped in the same failure handling the trace exporter uses. This runs from `AppConfig.ready()`, so a bad metrics endpoint or export interval would otherwise stop the service booting rather than degrading observability.
- Added a `django` extra carrying `opentelemetry-instrumentation-django[asgi]`. The instrumentor is what creates `http.server.duration` and `http.server.active_requests`, so without it a `MeterProvider` is installed and nothing feeds it. The `[asgi]` part is not optional in practice: ASGI support is gated behind it, and without it `_DjangoMiddleware` returns immediately on every ASGI request, emitting and logging nothing.

### Changed

- Raised the "no endpoint configured, tracing disabled" message from `debug` to `info`, and named the variables that would enable it. A service that silently exports nothing is indistinguishable from a healthy one until somebody goes looking in Tempo.
- The OTLP exporter startup log now names the configuration source (environment vs `OPENTELEMETRY_ENDPOINT`), since the URL finally posted to may differ from the configured value once the SDK appends a signal path.

### Fixed

- Fixed exception tracebacks in production JSON logs: foreign stdlib records (Django, third-party loggers) emitted with `exc_info=True` were serialised as raw Python object references instead of being rendered. A dedicated `ExceptionRenderer(ExceptionDictTransformer(show_locals=False, max_frames=20))` is now applied before `JSONRenderer` in both `configure_structlog()` and the `settings/logging.py` LOGGING dict path.
- Replaced the deprecated `structlog.processors.format_exc_info` with `ExceptionRenderer` using structured dict tracebacks, which Loki / Grafana can index by exception type, value, and frame metadata.

- Fixed `inject_otel_context()` dropping `trace_id`/`span_id` from logs whenever the current span was valid but not recording. It skipped exactly the traffic the head sampler declined — at a sampling ratio below 1.0 that is most Celery task logs, since a task starts a root span with no parent decision to inherit. The ids are now emitted for any valid span context, matching what OTel's own logging instrumentation does, so logs for one request stay correlatable across services even when the trace was never sampled into Tempo. The trade-off is that a Grafana logs-to-traces link can now point at a trace that was not kept.

- Fixed OTLP endpoint resolution defeating the SDK's signal-path handling. `configure_opentelemetry()` read `OTEL_EXPORTER_OTLP_ENDPOINT` itself and passed the value to `OTLPSpanExporter(endpoint=...)`, and an explicitly-passed endpoint is used verbatim — so setting the standard base URL (the spec-correct choice) produced POSTs to the collector root and a 404 per batch, surfaced as nothing louder than a `BatchSpanProcessor` warning. The exporter is now given an endpoint only when it came from the `OPENTELEMETRY_ENDPOINT` Django setting, which is a full signal URL; when the environment configures it, the SDK resolves it and appends `/v1/traces` as intended.
- Fixed `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` being ignored. Setting only the signal-specific variable left `endpoint` unset, so `configure_opentelemetry()` returned early and disabled tracing silently. Both standard variables are now recognised, most-specific first.
