# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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