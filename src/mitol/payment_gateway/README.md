mitol-django-payment_gateway
---

This is the Open Learning Django Payment Gateway app. Its purpose is to wrap up payment processing in a reasonably generic and pluggable way, so that payment processing is relatively straight-forward to implement in a given app. 

The payment gateway supports the following payment processors:
- CyberSource

Additional payment processors can be added in if necessary. 

### Setup

For CyberSource, you will need to set these things:

- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY```
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID```
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY```
- ```MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL```

All of these come from the CyberSource business center, under Secure Acceptance Settings in Payment Configuration. 

The Payment Gateway app needs no further confiruation. 

### Use

For specifics, see the PaymentGateway class in the api. 

1. Import the PaymentGateway class and the constants.
2. Assemble the information about the transaction you're about to process. There should be a set of line items representing the items to be purchased and some order metadata. You can optionally pass in custom data if your app requires that. You will also need to provide two URLs - one to display the receipt and one to handle transaction cancellation - that the processor will redirect the customer to once they've hit an end state in the payment processor workflow. 
3. Call ``start_payment`` with the payment processor to use (there's a constant defined for each supported one) and the data assembled in step 2. You should receive a dictionary back with the data you'll need to redirect the customer to so they can complete the purchasing process. 
4. Elsewhere in your app, provide handlers for the receipt display and cancel endpoints. How these will work specifically will depend on the processor(s) being used. 

The custom data (merchant_fields) should be a list of items to pass along with the transaction data. Each processor will handle this data differently (if the processor supports it at all). For CyberSource, things passed in merchant_fields get enumerated out into the "merchant_defined_dataX" fields that are available in its API. 

### Adding Gateways

Adding a new gateway consists of adding in the gateway class itself, adding necessary configuration settings, and adding in a new constant to name the gateway. 

The class itself needs to implement a single method: ```prepare_checkout```, which should accept all the pertinent order information, perform any processing needed to make it suitable for the payment processor, and return back the data to send to the customer so they can start the actual purchasing process. 

The data returned from a successful ```prepare_checkout``` call should be a dictionary containing:
- ```method``` - the HTTP method that the customer's browser should use (typically, this is POST but some payment processors may require other things)
- ```url``` - the URL to send the customer to
- ```payload``` - the data to send to the aforementioned URL
Generally, you'll need to construct a form in the front end to POST the payload data to the URL specified in the customer's browser, and the customer then completes the process on the payment processor's site. 

The CyberSource gateway can be used as a template for future gateways. Most of the internal methods in it contain CyberSource-specific implementation details, but it should illustrate how to add in a new processor. 