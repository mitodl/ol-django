### Fixed

- The `HubspotObject` admin changelist no longer runs one query per row to load `content_object`; each page now prefetches it with one query per content type. Rows whose content type points at a removed model are left out of the prefetch, so they still render.
