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
  Bulk create) and `error` (the operation's error body on failure), so callers
  can verify what was actually stored without making additional API calls.

### Changed

- **Breaking:** `sync_users_to_scim_remote` now yields `UserState` results as
  a generator instead of returning `None`. It does nothing until iterated -
  existing callers that discarded the return value (e.g.
  `sync_users_to_scim_remote_batch`) must now iterate or drain it (e.g.
  `deque(sync_users_to_scim_remote(users), maxlen=0)`) for the sync to run at
  all. A caller that needs a concrete list should wrap a single, bounded call
  in `list(...)` itself - materializing every `UserState` (each now carrying
  a full response body) for an unbounded `users` list risks exhausting
  memory, which this generator-based API avoids by construction.

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
