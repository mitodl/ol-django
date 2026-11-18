### Added

- Added a `PaymentMethodType` model, and a `StripePaymentMethodType` proxy model
  that decodes its Stripe data, for payment methods a gateway has to request
  explicitly at checkout (such as a custom PayPal payment method in Stripe).
- `StripePaymentGateway.prepare_checkout` accepts a `payment_method_types` keyword
  argument. Without it, the default `StripePaymentMethodType`s are sent to Stripe
  as `custom_payment_method_types` and `payment_method_types`; an empty list sends
  none.
- Added the `MITOL_PAYMENT_GATEWAY_STRIPE_ENABLE_PAYMENT_METHOD_TYPES` setting
  (off by default). Payment method types are only sent to Stripe when it is on.
