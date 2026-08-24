### Changed

- `UserGlobalIdMixin.global_id` is now `unique=True`, with unset stored as `NULL` (`null=True, default=None`) rather than `""`. It is the identity key an API gateway resolves users by, and without the constraint a get-then-create under concurrency silently forks an account in two. Unset has to be NULL because SQL treats NULLs as distinct under a unique constraint and empty strings as equal — keeping `""` would cap an estate at exactly one out-of-band user.

  **Consumers need a migration, and it must be three steps, not one.** Widen the column to `null=True`, migrate `""` to `NULL`, then add the constraint — adding it in a single `AlterField` fails on any estate holding more than one unlinked user, which is every estate that has one. See `testapp/users/migrations/0006_user_global_id_unique.py` for the shape.

  **Check for duplicate non-empty `global_id`s before migrating.** Those are genuinely forked accounts; the constraint will refuse them, which is the point, but they need merging first rather than discovering it during a deploy.

  Apps that already declare their own `global_id` are unaffected — mitxonline and mit-learn both already independently reached `null=True, unique=True`.
