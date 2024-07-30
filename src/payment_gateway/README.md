mitol-django-payment_gateway
---

This is the Open Learning Django Payment Gateway app. Its purpose is to wrap up payments and refunds processing in a reasonably generic and pluggable way, so that payment and refund processing is relatively straight-forward to implement in a given app.

The payment gateway supports the following payment processors:
- CyberSource

Additional payment processors can be added in if necessary.

### Setup

Add the payment_gateway app:

```python
INSTALLED_APPS = [
    ...
    "mitol.payment_gateway.apps.PaymentGatewayApp",
]
```

Add/Append this to your settings file:
```python
# Imports the default cybersource settings defined in mitol-django-payment-gateway for CyberSource (There might be other gateways in future)
from mitol.common.envs import import_settings_modules
import_settings_modules(globals(), "mitol.payment_gateway.settings.cybersource")
```

For CyberSource, you will need to set a couple of keys (Details below):

- ```ECOMMERCE_DEFAULT_PAYMENT_GATEWAY``` - The current default value for this is `CyberSource`. In future when there are more gateways it will be the values for the gateway to be used.

**Secure Acceptance Keys**

The below settings come from the CyberSource business center, under Secure Acceptance Settings in Payment Configuration.

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY``` - Access key from CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID``` - Profile Id of CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY``` - Security key for CyberSource Secure Acceptance
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL``` - Secure Acceptance URL of your Cybersource account

**CyberSource REST API keys**

The below settings come from the CyberSource business center, under Payment Configuration->Key Management->REST APIs.

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID``` - Merchant id same as used for processing payments in CyberSource (e.g. SecureAcceptance)
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET``` - Merchant secret for the CyberSource REST APIs
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID``` - Merchant secret key id for the CyberSource REST APIs

Values that do not come from CyberSource account directly:

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT``` - The current default value for this is `apitest.cybersource.com`. The possible values are (`apitest.cybersource.com` - For Test CyberSource REST API and `api.cybersource.com` - For Production CyberSource REST API).


The Payment Gateway app needs no further configuration.

### Usage

For specifics, see the PaymentGateway class in the api.

**For processing a payment (Secure Acceptance)**
1. Import the PaymentGateway class and the constants.
2. Assemble the information about the transaction you're about to process. There should be a set of line items representing the items to be purchased and some order metadata. You can optionally pass in custom data if your app requires that. You will also need to provide two URLs - one to display the receipt and one to handle transaction cancellation - that the processor will redirect the customer to once they've hit an end state in the payment processor workflow.
3. Call ``start_payment`` with the payment processor to use (there's a constant defined for each supported one) and the data assembled in step 2. You should receive a dictionary back with the data you'll need to redirect the customer to so they can complete the purchasing process.
4. Elsewhere in your app, provide handlers for the receipt display and cancel endpoints. How these will work specifically will depend on the processor(s) being used.

The custom data (merchant_fields) should be a list of items to pass along with the transaction data. Each processor will handle this data differently (if the processor supports it at all). For CyberSource, things passed in merchant_fields get enumerated out into the "merchant_defined_dataX" fields that are available in its API.

**For processing a refund (CyberSource REST API)**
1. Import the PaymentGateway, Refund classes and the constants.
2. Assemble the information(transaction_id, refund_amount, refund_currency) about the refund you're about to process. You would probably get this data from your existing completed payments.
3. Call ``start_refund`` with the payment processor(e.g. CyberSource) to use (there's a constant defined for each supported one) and the data assembled in step 2.

**Refund Code Example:**

```python
from mitol.payment_gateway.api import PaymentGateway
      # Create a Refund request object to perform operations on
      refund_gateway_request = PaymentGateway.create_refund_request(
          ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
          transaction_dict  # Ideally this dict should have transaction_id, req_amount, req_currency
      )

      # Call start_refund from PaymentGateway with the Refund object you just created above
      response = PaymentGateway.start_refund(
          ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,    # Default Gateway to be used for processing e.g. CyberSource
          refund_gateway_request,
      )


```

### Adding Gateways

Adding a new gateway consists of adding in the gateway class itself, adding necessary configuration settings, and adding in a new constant to name the gateway.

The class itself needs to implement methods:
- ```prepare_checkout```, which should accept all the pertinent order information, perform any processing needed to make it suitable for the payment processor, and return back the data to send to the customer so they can start the actual purchasing process.
- ```perform_refund```, which should accept an object of `mitol.payment_gateway.api.Refund` with the required data set in the object.

The data returned from a successful ```prepare_checkout``` call should be a dictionary containing:
- ```method``` - the HTTP method that the customer's browser should use (typically, this is POST but some payment processors may require other things)
- ```url``` - the URL to send the customer to
- ```payload``` - the data to send to the aforementioned URL
Generally, you'll need to construct a form in the front end to POST the payload data to the URL specified in the customer's browser, and the customer then completes the process on the payment processor's site.


The data returned from a ```perform_refund``` call could be:

- For a successful refund you should receive a `ProcessorResponse` object back with refund details(i.e. state, message, response_date etc.)
- In case of failure:
    - If the request fails because of duplication, you would receive `RefundDuplicateException` with details so that you can decide how you want to treat it (e.g. Duplicate request is considered as success for MITxOnline, but it might be different for other applications).
    - For all other failures you would receive a general exception(i.e. `CyberSource.rest.ApiException`) with details so that you can handle your this failure appropriately in your application.


The CyberSource gateway can be used as a template for future gateways. Most of the internal methods in it contain CyberSource-specific implementation details, but it should illustrate how to add in a new processor.
