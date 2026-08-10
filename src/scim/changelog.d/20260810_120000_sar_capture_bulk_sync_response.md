<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
### Added

- `UserState` now carries `response_body` (the echoed resource on a successful
  Bulk create) and `error` (the operation's error body on failure).
  `sync_users_to_scim_remote` now returns the full list of `UserState` results
  instead of `None`, so callers can verify what was actually stored without
  making additional API calls.

<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
<!--
### Fixed

- A bullet item for the Fixed category.

-->
<!--
### Security

- A bullet item for the Security category.

-->
