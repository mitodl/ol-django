### Changed

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.
- Converted all 3 admin registrations from `admin.site.register(Model, ModelAdmin)` to the `@admin.register(Model)` decorator. No behaviour change.

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.
