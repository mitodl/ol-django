# CyberSource Secure Acceptance Integration for Payment Gateway

> ![WARNING]
> CyberSource Secure Acceptance reaches end-of-life on August 31, 2026.

To make the CyberSource integration work, you will need to gather some configuration settings. For the most part, these are available through the Enterprise Business Center. Contact your manager for access to the CyberSource EBCs.

For local development, you can also set up a personal development account. That is (currently) done here: https://developer.cybersource.com/hello-world/sandbox.html You will have to configure the account to enable Secure Acceptance and get the requisite keys below, and you'll have to set up the payment process to accept credit cards. In addition, a common point of failure is accepted currencies; you should make sure you've set up your account to accept USD.

An easier option (unless you need EBC access and don't currently have an account) is to scrape these values off of the QA/CI tier of an integrated app. These tiers also use sandbox accounts and are already set up close to how production is set up.

**Secure Acceptance Keys**

These settings are used for payment processing and are required.

The below settings come from the CyberSource business center, under Secure Acceptance Settings in Payment Configuration.

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY``` - Access key from CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID``` - Profile Id of CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY``` - Security key for CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL``` - Secure Acceptance URL of your Cybersource account

**CyberSource REST API keys**

These settings are used for initiating returns and other out-of-band tasks, and are not strictly required for local testing.

The below settings come from the CyberSource business center, under Payment Configuration->Key Management->REST APIs.

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID``` - Merchant id same as used for processing payments in CyberSource (e.g. SecureAcceptance)
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET``` - Merchant secret for the CyberSource REST APIs
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID``` - Merchant secret key id for the CyberSource REST APIs

Values that do not come from CyberSource account directly:

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT``` - The current default value for this is `apitest.cybersource.com`. The possible values are `apitest.cybersource.com` for Test CyberSource REST API and `api.cybersource.com` for Production CyberSource REST API.

**Keeping the genuine urllib3**

`cybersource-rest-client-python` depends on `urllib3-future` rather than `urllib3`. The `urllib3-future` wheel ships a top-level `urllib3` package and a `.pth` file that copies it over `site-packages/urllib3` whenever the interpreter starts, so installing it replaces the urllib3 that requests, botocore, and sentry-sdk use for the whole environment.

To keep the genuine urllib3, install a metadata-only `urllib3-future` in its place. The name has to be installed, because the SDK's `ApiClient` calls `pkg_resources.require("cybersource-rest-client-python")`, which checks every declared requirement. With uv, add a local project that declares the name and ships no code:

```toml
# shims/urllib3-future/pyproject.toml
[project]
name = "urllib3-future"
version = "0.0.0"
requires-python = ">=3.11"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = []
```

and point your project at it:

```toml
[project]
dependencies = [
    # ...
    "urllib3-future",
]

[tool.uv.sources]
urllib3-future = { path = "shims/urllib3-future" }
```

Copy the `shims/` directory into your image before `uv sync`. ol-django's own workspace does the same (see `shims/urllib3-future/pyproject.toml` at the repo root).

The SDK also passes `keepalive_delay` and `keepalive_idle_window` to `urllib3.PoolManager`, and only urllib3-future accepts those. `PaymentGatewayApp.ready()` applies `mitol.payment_gateway.cybersource_compat.apply_cybersource_urllib3_compat()`, which removes those arguments before they reach urllib3, so no application code is needed for that part. Applications that carried their own copy of this patch can delete it.
