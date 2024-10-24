
.. _changelog-2024.10.24:

2024.10.24 — 2024-10-24
=======================

### Changed

- Added posthog application.

Added
-----

- Migrated the MaxMind GeoIP code from xPRO into a ol-django app.
- Added a new management command (`create_private_maxmind_data`) to create GeoIP data for local networks.

Changed
-------

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

- Updated faker dependency to start at 4.17 (rather than requiring it)

.. _changelog-2023.12.19.1:

2023.12.19.1 — 2023-12-19
=========================

Added
-----

- Migrated the MaxMind GeoIP code from xPRO into a ol-django app.
- Added a new management command (`create_private_maxmind_data`) to create GeoIP data for local networks.

Changed
-------

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.
