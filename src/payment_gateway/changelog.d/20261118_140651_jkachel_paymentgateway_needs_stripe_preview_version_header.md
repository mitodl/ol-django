### Fixed

- `StripePaymentGateway.prepare_checkout` now sends a `.preview` Stripe API
  version when the Checkout Session includes `custom_payment_method_types`, which
  Stripe rejects otherwise. Sessions without custom payment methods still use the
  default API version.

### Added

- Added the `MITOL_PAYMENT_GATEWAY_STRIPE_PREVIEW_API_VERSION` setting to choose
  the preview API version. If it is not set, the Stripe SDK's API version date is
  used with a `.preview` suffix (e.g. `2026-08-26.preview`).
