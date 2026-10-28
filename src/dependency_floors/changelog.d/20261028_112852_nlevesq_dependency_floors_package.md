### Added

- Initial release. `dependency-floors check` verifies that a repository's
  manifests and lockfile enforce the dependency version floors declared in
  `[tool.dependency-floors]`.
- Lockfile checks that apply to any repository: `lock-below-floor` catches a
  resolution that has fallen under a floor, which is how a release-age cooldown
  silently undoes a security bump; `constraint-below-floor` catches a resolver
  constraint drifting away from the floor it guards.
- Publishing checks for workspaces: `floor-not-declared`,
  `inherited-floor-unpinned`, `floor-declared-redundantly` and
  `floor-not-needed` decide, per member and per extra, whether a package has to
  declare a floor itself, inherit it from a pinned sibling, or carry nothing.
- `dependency-floors explain <floor>` prints each member's classification and
  the dependency path behind it.
