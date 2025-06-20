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

username generation functionality:

- usernameify() - Generate usernames from full names with email fallback
- create_user_with_generated_username() - Create users with automatic username collision handling
- _find_available_username() - Handle username conflicts by appending numeric suffixes
- _reformat_for_username() - Clean and format strings for username use
- is_duplicate_username_error() - Detect database integrity errors for username collisions

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
