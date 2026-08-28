# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.8.28'></a>
## [2026.8.28] - 2026-08-28

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Added

- Stripe: Additional constants for various Stripe and related values
- Stripe: Event filtering helper
- Stripe: Checkout session status calculation (including payment intent)
- Stripe: Fixtures based on the sample data from the docs

### Changed

- Stripe: Updated factories to use the new "real-data" fixtures
- Stripe: Moved test factories into the main app, so they can be used in dependent app

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

### Fixed

- Capped `cybersource-rest-client-python` below `0.0.64`. The constraint was an open `>=0.0.59`, so a lockfile refresh moved it 0.0.63 → 0.0.78, and 0.0.78 renames `Ptsv2paymentsProcessingInformationAuthorizationOptionsInitiatorMerchantInitiatedTransaction` to `ProcessingInfoAuthorizationOptionsInitiatorMerchantInitiatedTransaction`. Nothing in the library source references that class — the three model classes it does import all survive the bump — so no consumer was broken at runtime, but the test suite failed with `AttributeError` on every matrix job. The cap is an upper bound rather than an exact pin so consuming applications are not handed a hard conflict; moving to a newer SDK should be a deliberate, reviewed change rather than a side effect of relocking.

<a id='changelog-2026.8.10'></a>
## [2026.8.10] - 2026-08-10

### Added

- Added refund support to the Stripe payment gateway.

<a id='changelog-2026.8.5'></a>
## [2026.8.5] - 2026-08-05

### Added

- Added dependency on stripe-python.
- Added implementation of PaymentGateway for Stripe.
- Minor adjustments made to settings - now, just import the root app-level settings

### Changed

- Made the Stripe API key setting optional
- Added a check to the StripePaymentGateway to ensure it has an API key if it's being used
- Added some constants for Stripe data

<a id='changelog-2026.7.15'></a>
## [2026.7.15] - 2026-07-15

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

<a id='changelog-2025.3.6'></a>
## [2025.3.6] - 2025-03-06

### Added

- Adds support for tax collection.
- Bumps CyberSource REST Client package to at least 0.0.54.
- Adds a helper for quantizing decimals for currency amounts.

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

- Added posthog application.

- Update paths in pyproject.toml to ensure versioning continues to work.

- Removes unnecessary noqa's.

- Wrap the imports for CyberSource; they generate `SyntaxWarning`s, so this should quiet them down (and allow them to pass tests)

### removed

- support for python 3.8 and 3.9.

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.
## [1.9.0] - 2023-02-10

### Changed
- Adds transaction search and lookup to the CyberSource payment gateway.

## [1.8.0] - 2023-01-17

## [1.8.0] - 2023-01-17

## [1.7.1] - 2022-10-24

## [1.7.0] - 2022-08-04

## [1.6.0] - 2022-07-07

## [1.5.0] - 2022-06-29

## [1.4.0] - 2022-06-10

### Changed
- Adds hashing to the order username to get around CyberSource field limitations

## [1.2.2] - 2022-02-24

### Changed
- Bump `mitol-django-common` to `2.2.0`.

### Added
- Bug fix for CyberSource order extraction

## [1.2.1] - 2022-02-11

### Added
- Bug fix for CyberSource processor validation

## [1.2.0] - 2022-02-02

### Added
- Added get_formatted_response helper to decode processor responses into a generic format
- Added ProcessorResponse dataclass to provide a standard interface for processor responses

## [1.1.0] - 2022-01-24

### Added
- Added validate_processor_response helper for creating authentication classes

## [1.0.0] - 2022-01-20

### Added
- Added `mitol-django-payment_gateway` app
- Added CyberSource payment gateway implementation
