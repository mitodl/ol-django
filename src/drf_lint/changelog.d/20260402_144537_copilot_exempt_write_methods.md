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
### Deprecated

- A bullet item for the Deprecated category.

-->
### Changed

- Serializer write-path methods (`validate`, `validate_<field>`, `create`, `update`, `to_internal_value`) are now exempt from ORM N+1 checks. These methods only execute during POST/PATCH/PUT operations on a single resource, making N+1 detection inapplicable.

<!--
### Fixed

- A bullet item for the Fixed category.

-->
<!--
### Security

- A bullet item for the Security category.

-->
