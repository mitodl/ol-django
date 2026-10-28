### Changed

- Require `mitol-django-common>=2026.10.29`, the first release that declares
  the `certifi>=2026.10.19` floor for the eMudhra CA compromise
  ([GHSA-6q48-6c7w-9gw2][advisory]). This package reaches certifi only through
  `mitol-django-common`, so it inherits the floor rather than declaring one of
  its own — but the dependency was previously unpinned, which an older release
  predating the floor would have satisfied.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2
