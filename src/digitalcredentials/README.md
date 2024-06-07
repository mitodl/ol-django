mitol-django-digital-credentials
---

This is the Open Learning Django Digital Credentials app. Provides the following functionality:

- Data models:
  - `DigitalCredentialRequest` - a one-time use credential request that is bound to a courseware object and a learner
  - `LearnerDID` - a record of which DID(s) are bound to any given user. This guarantees we won't allow a DID to be used for a different user once bound.
  - `DigitalCredential` - a record of the signed digital credential, the courseware object, and the learner whom it is for
- Django admin UI for these models
- `/credentials/request/<uuid>/` API for requesting credentials
  - Requires OAuth2 authentication provided by `django-oauth-toolkit`


### Getting started

`pip install mitol-django-digital-credentials`

Add the digital credentials app:

```python
INSTALLED_APPS = [
    ...
    "mitol.digitalcredentials.apps.DigitalCredentialsApp",
]
```

### Settings

#### Common Django settings

- `SITE_BASE_URL` - the website's host url, including the protocol (e.g. "https://example.com/")


#### Digital Credentials app settings

- `MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL` - the base url for the hosted `sign-and-verify` service
- `MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC` - a function to build the credential document
