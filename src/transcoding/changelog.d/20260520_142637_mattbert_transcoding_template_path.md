### Added

- `media_convert_job()` and `make_media_convert_job()` now accept an optional `template_path` argument that overrides `settings.TRANSCODE_JOB_TEMPLATE` for a single call. This lets a project dispatch jobs through multiple templates (e.g. landscape vs. portrait pipelines) without mutating settings.
