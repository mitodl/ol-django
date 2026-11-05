### Changed

- Raised the minimum supported Django to 5.2. Django 4.2 reached end of life on
  2026-04-07, and 5.0 and 5.1 before it (2025-04-02 and 2025-12-03), leaving
  5.2 as the only supported LTS, so the 4.2, 5.0 and 5.1 CI legs are gone.
- `CheckConstraint` now passes `condition=` directly. The version gate that
  chose between `check=` and `condition=` picked `check=` only below Django
  5.1, which a 5.2 floor excludes, so that branch was unreachable. The same
  gate is removed from the historical `0001_add_geoip_tables` migration, which
  produces the identical constraint.
