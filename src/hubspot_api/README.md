mitol-django-hubspot-api
---

This is the Open Learning Hubspot API integration app. It provides helper functions for Hubspot CRM API calls:

- CRUD functions for custom properties and property groups
- CRUD functions for deals, line items, products, and contacts
- Search/retrieve specific objects or lists of objects of a certain type

### Getting started

`pip install mitol-django-hubspot-api`

Add the hubspot app:

```python
INSTALLED_APPS = [
    ...
    "mitol.hubspot_api.apps.HubspotApp",
]
```

### Settings

#### Hubspot app settings

All settings for the `mitol-django-hubspot-api` app are namespaced in django settings with `MITOL_HUBSPOT_API` prefix.

- `MITOL_HUBSPOT_API_PRIVATE_TOKEN` - the private app token to be used for authentication (required)
- `MITOL_HUBSPOT_API_RETRIES` - the number of times to retry API calls on failures (default=3)
- `MITOL_HUBSPOT_API_ID_PREFIX` - a prefix used for generating custom unique object ids (default="app")

### Usage

#### Instantiate an API client to make custom hubspot requests

```python
from mitol.hubspot_api.api import HubspotApi, HubspotObjectType

client = HubspotApi()
client.crm.objects.basic_api.update(
    simple_public_object_input=input_body,
    object_id=123,
    object_type=HubspotObjectType.DEALS.value,
)
```

#### Use helper functions to make common hubspot requests
```python
from mitol.hubspot_api.api import find_product

hubspot_product = find_product("Product #1", price="123.99")
```
