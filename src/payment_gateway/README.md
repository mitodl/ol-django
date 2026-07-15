mitol-django-payment_gateway
---

This is the Open Learning Django Payment Gateway app. Its purpose is to wrap up payments and refunds processing in a reasonably generic and pluggable way, so that payment and refund processing is relatively straight-forward to implement in a given app.

The payment gateway supports the following payment processors:
- [CyberSource](README-CyberSourceSA.md)
- [Stripe](README-Stripe.md)

Additional payment processors can be added in when necessary.

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
# Imports the Payment Gateway settings
from mitol.common.envs import import_settings_modules
import_settings_modules(globals(), "mitol.payment_gateway.settings")
```

The Payment Gateway has one setting that needs to be configured:

- ```ECOMMERCE_DEFAULT_PAYMENT_GATEWAY``` - This is set to the gateway name as set in [src/constants.py](src/constants.py). This defaults to **`"None"`**. This is a convenience setting but leaving it unset may break apps that use it.

You will additionally want to read through the documentation for the gateway you wish to use as it will have its own settings to configure.

### Usage

For specifics, see the PaymentGateway class in the api and the linked documentation above.

**For processing a payment**
1. Import the PaymentGateway class and the constants.
2. Assemble the information about the transaction you're about to process.
   a. There should be a set of line items representing the items to be purchased and some order metadata. You can optionally pass in custom data if your app requires that.
   b. You should also have two URLs set up. These are used as the redirect target for the user - once they have completed payment (successfully or not), the system will send them to one of these URLs. One is a receipt/success URL and one is a cancel URL. These can be passed in `start_payment` or they can usually be configured in the payment processor settings (the CyberSource EBC or the Stripe Dashboard, etc.).
   c. For CyberSource SA specifically, you can also specify a custom "backoffice" URL. This is a webhook location that instructs CyberSource where to post events about the order. This can also be configured in the EBC; you don't explicitly have to supply this per transaction.
3. Call ``start_payment`` with the payment processor to use (there's a constant defined for each supported one) and the data assembled in step 2. You should receive a dictionary back with the data you'll need to redirect the customer to so they can complete the purchasing process.
    a. If the returned data sets `method` to `POST`, then you're expected to use the payload to create an HTML form that the user then has to submit to the supplied URL. (Generally, you'd build this out and submit it automatically using JavaScript.) This does need to be a regular form within the page - the user needs to end up at the action URL set.
    b. If the returned data sets `method` to `GET`, you're expected to redirect the user to the action URL. No other processing is needed.
4. Elsewhere in your app, provide handlers for the receipt display and cancel endpoints. How these will work specifically will depend on the processor(s) being used.

The custom data (merchant_fields) should be a list of items to pass along with the transaction data. Each processor will handle this data differently (if the processor supports it at all) and there are usually limits what can be passed. For CyberSource, things passed in merchant_fields get enumerated out into the "merchant_defined_dataX" fields that are available in its API. Stripe allows for any arbitrary key/value pairs but each pair has limits on data size.

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
- ```method``` - the HTTP method that the customer's browser should use (CyberSource expects a `POST`ed form, Stripe expects you to redirect the customer so it sets this to `GET`.)
- ```url``` - the URL to send the customer to
- ```payload``` - the data to send to the aforementioned URL

Generally, you'll need to construct a form in the front end to POST the payload data to the URL specified in the customer's browser, and the customer then completes the process on the payment processor's site.

The data returned from a ```perform_refund``` call could be:

- For a successful refund you should receive a `ProcessorResponse` object back with refund details(i.e. state, message, response_date etc.)
- In case of failure:
    - If the request fails because of duplication, you would receive `RefundDuplicateException` with details so that you can decide how you want to treat it (e.g. Duplicate request is considered as success for MITxOnline, but it might be different for other applications).
    - For all other failures you would receive a general exception(i.e. `CyberSource.rest.ApiException`) with details so that you can handle your this failure appropriately in your application.

The CyberSource gateway can be used as a template for future gateways. Most of the internal methods in it contain CyberSource-specific implementation details, but it should illustrate how to add in a new processor.
