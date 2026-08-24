### Fixed

- `SCIMUser.from_dict` wrote `""` to `global_id` when the payload carried no `externalId`. Now that the field is unique, the second such user would have collided; it writes `None`.
- `sync_all_users_to_scim_remote(never_synced_only=True)` selected never-synced users with `global_id=""`, which stopped matching once unset became `NULL` — it would have silently synced nobody. It now matches either empty.
