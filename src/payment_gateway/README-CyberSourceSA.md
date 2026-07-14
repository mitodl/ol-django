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
