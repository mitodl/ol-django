### Added

- `mitol.common.utils.config.SettingsRef`, a non-data descriptor for class attributes that are backed by a Django setting. It reads the setting on access, so `override_settings` reaches an object that already exists, and an instance attribute still shadows it by the normal attribute lookup rules — assignment, `del` and `mock.patch.object` all behave as they do for a plain attribute.

  Use it in place of reading a setting into a class attribute at import time or into an instance attribute in `__init__`. Both freeze the value; for a module-level singleton that means a test can never override it.
