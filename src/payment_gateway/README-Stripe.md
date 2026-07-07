# Configuring Stripe for Payment Gateway

Testing and using Stripe is relatively easy. Stripe makes available several developer tools, including a Web console and a command line client, that help with a lot of local development use cases.

## Prerequisite setup

**Create a Stripe account:** Sign up for a Stripe account at https://stripe.com . Accounts are free. You don't need to fully complete the onboarding process - once it starts offering you the option to skip steps or close out of setup modals, you can do so without issue, and the account will work in sandbox mode.

**Retrieve API keys and use the Workbench:** Once you're logged into the Stripe dashboard, you should be able to see the Developers menu at the bottom left. This menu gives you access to various things within the Stripe Developer tools, including API keys. The Workbench is also available under this menu - of note is the Events and Logs tabs, which will show you data that is passing through the sandbox.

**Install the Stripe CLI:** The Stripe CLI provides a pretty useful way to access a lot of API features, and offers a "listen" feature that is specifically very helpful for webhook development. Install the CLI: https://docs.stripe.com/stripe-cli/install The CLI is optional but recommended for local development.

## API Keys

The Stripe API uses a single API key for API access. For testing, you can use the test mode key (starting with `sk_test_` per the documentation) which allows access for all API endpoints. For deployment, a restricted API key can be created that has access only specified APIs. The payment gateway settings include a setting for this key - `MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY`.

When Stripe sends data via webhook, it includes a shared secret that "signs" the payload. Note that the payload itself is not encrypted - the secret is included essentially as authentication for the endpoint. These secrets are generated when the webhook endpoints are set up in the Dashboard, and are also delivered in the response if the endpoint is registered through the API. Secrets are not sent when querying the webhook endpoint API. If the app is configured to verify the payload (which is recommended), these secrets need to be stored in a reasonable way and provided to the validation functions.

## Webhook Development and Configuration

Stripe will use webhooks to notify the app when events are triggered. The most immediate use case for this are transaction and refund status events. To work with and test these locally, you will need to configure a system that allows Stripe to access your app's webhook endpoints that are running locally. There are a handful of ways to do this.

By far, the easiest option is to use the Stripe CLI for this purpose. The `stripe listen` command listens for events within your sandbox and optionally redirects them to the appropriate endpoint on your local system. To use the CLI to just log the event data to the terminal, run `stripe listen --format json`. To also have it proxy the events to your application (or some other service), append `--forward-to <url>`. The URL specified can be a local one - as long as you can reach it yourself, it's a valid target for `--forward-to`. The Stripe client manages the data flow for this so it will work without needing to set up any other ingress systems (such as ngrok).

For testing within `ol-django` specifically, you may want to configure a standalone webhook collection service to capture the requests and provide to you the submitted data. There are a few options for this:

- You can run a service that does this in a separate container, and then set up ingress so that Stripe can hit the endpoints.
	- There are a handful of generic webhook endpoint apps that are available: https://hub.docker.com/r/tecktron/webhook_catcher https://github.com/tarampampam/webhook-tester or https://hub.docker.com/r/webhooksite/webhook.site are all reasonable choices. These give you an endpoint (or multiple endpoints) that can be hit; data sent in is collected and displayed with the app somewhere. (You can also write a quick one yourself if you want.)
	- You then need to set up an ingress controller to allow access to the webhook app. This can be something like ngrok, or a Cloudflare tunnel, or Tailscale `publish`, or something along those lines. You can also use the Stripe CLI as noted above - `stripe listen --forward-to http://localhost` is a perfectly valid way to do it.
- You can use a third-party service for this. For instance, the webhooksite Docker image is also available as a cloud service: https://webhook.site .

If you're not using the Stripe CLI to proxy requests into the webhook endpoint, you will need to configure the endpoints within the Stripe Dashboard. The Webhooks option under the Developers menu at the bottom will walk you through the process.

When configuring webhooks, you will be prompted to specify what kind of data the endpoint expects - either a snapshot or thin. Ensure that you're setting up the endpoints to receive **snapshot** results. The payment gateway implementation is written to use the snapshot result type, and the two types are not compatible with each other.

## Other Testing Notes

In sandbox mode, the system will not generate actual charges. However, you should not use a real credit card number for testing. The Stripe documentation describes how to use a test card: https://docs.stripe.com/testing#use-test-cards They also provide an extensive list of test card numbers that cover a wide range of potential use cases, including numbers configured for international (non-US) payment and various different brands.

The test card documentation also includes some documentation on what values to use in automated tests that use the Stripe API. However, the payment gateway does not support specifying the payment method as part of the checkout session setup at this point. Instead, mock the Stripe API if you are writing tests that involve processing responses from Stripe; our tests should generally not hit external APIs.
