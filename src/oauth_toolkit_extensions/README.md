mitol-django-oauth-toolkit-extensions
---

This is the Open Learning's extensions to `django-oauth-toolkit`.

### Getting started

`pip install mitol-django-oauth-toolkit-extensions`


### Configuration


Add the following to `settings.py`:

```python
INSTALLED_APPS = [
    ...
    "mitol.oauth_toolkit_extensions.apps.OAuthToolkitExtensionsApp",
]

# required for migrations
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'oauth2_provider.AccessToken'
OAUTH2_PROVIDER_APPLICATION_MODEL = 'oauth2_provider.Application'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'oauth2_provider.RefreshToken'

OAUTH2_PROVIDER = {
    ...
    # enable the custom scopes backends
    "SCOPES_BACKEND_CLASS": "mitol.oauth_toolkit_extensions.backends.ApplicationAccessOrSettingsScopes",
}
```


### Usage

After installing this app, a modified `Application` django-admin interface (/admin/oauth2_provider/application/) is available that allows you to optionally create an `ApplicationAccess` record. If you create this record, it will limit scope authorization to the scopes specified in that record. Otherwise the allowed scopes will be derived from settings.
