<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
<!--
### Added

- A bullet item for the Added category.

-->
<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
### Fixed

- Fixed exception tracebacks in production JSON logs: foreign stdlib records (Django, third-party loggers) emitted with `exc_info=True` were serialised as raw Python object references instead of being rendered. A dedicated `ExceptionRenderer(ExceptionDictTransformer(show_locals=False, max_frames=20))` is now applied before `JSONRenderer` in both `configure_structlog()` and the `settings/logging.py` LOGGING dict path.
- Replaced the deprecated `structlog.processors.format_exc_info` with `ExceptionRenderer` using structured dict tracebacks, which Loki / Grafana can index by exception type, value, and frame metadata.

### Added

- Added `celery`, `celery.task`, `celery.worker`, and `django_structlog` loggers to the stdlib logging configuration in both `configure_structlog()` and `settings/logging.py`, so Celery worker output and `django-structlog` context propagation logs are routed through the structlog formatter.
- Added `force` parameter to `configure_structlog()` to support Celery worker processes where logging must be re-applied after Celery resets the logging configuration.
<!--
### Security

- A bullet item for the Security category.

-->
