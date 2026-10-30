
<a id='changelog-2026.10.30'></a>
## [2026.10.30] - 2026-10-30

### Removed

- Removed support for Python 3.10

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

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
