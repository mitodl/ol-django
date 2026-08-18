<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Added

- A bullet item for the Added category.

-->
<!--
### Removed

- A bullet item for the Removed category.

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

- `UserState.error` on a failed Bulk operation now holds the nested SCIM
  error body (`operation["response"]`) instead of the entire Bulk operation
  envelope, matching what's documented and what `response_body` already does
  for successful operations.

<!--
### Security

- A bullet item for the Security category.

-->
