### Fixed

- `SCIMUser.from_dict` wrote `""` to `global_id` when the payload carried no `externalId`. Now that the field is unique, the second such user would have collided; it writes `None`.
- `sync_all_users_to_scim_remote(never_synced_only=True)` selected never-synced users with `global_id=""`. Most matched anyway through its other `scim_external_id=None` clause, but a user with `global_id` unset and a `scim_external_id` already populated would have stopped matching once unset became `NULL`. It now matches either empty representation of `global_id` directly.
