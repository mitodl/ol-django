
<a id='changelog-2026.3.6'></a>
## [2026.3.6] - 2026-03-06

### Added

- Added posthog application.

- Added a time-based circuit breaker to PostHog feature flag evaluation. If PostHog calls are slow or failing, the circuit opens and subsequent calls return default values immediately, preventing PostHog outages from degrading service for users. The trip threshold and cooldown are configurable.
- Added support for local evaluation of PostHog feature flags via `POSTHOG_PERSONAL_API_KEY`. When set, flag definitions are retrieved locally and evaluated without hitting PostHog, reducing latency and outage impact.

### Changed

- Version date from using 04 to 4.

<a id='changelog-2025.8.1'></a>
## [2025.8.1] - 2025-08-01

### Added

- Added posthog application.

### Changed

- Version date from using 04 to 4.

- Updated PostHog dependency to >=6.3.1,<7.

### Fixed

- Renamed `api_key` to `project_api_key` named keyword argument when creating PostHog client after posthog update.

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

### Added

- Added posthog application.

### Changed

- Version date from using 04 to 4.

- Update paths in pyproject.toml to ensure versioning continues to work.

### added

### removed

- support for python 3.8 and 3.9.
