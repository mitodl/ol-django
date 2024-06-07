mitol-django-olposthog
---

This is the Open Learning OlPosthog app. It provides an API to interact with Posthog in order to check feature flags.


### Installation and setup

Add the OlPosthog app:

`docker-compose run -u root --rm web poetry add mitol-django-olposthog`

Add the following to the `ready()` method for your App.

```
from mitol.olposthog.features import configure
configure()

```

#### Common Django settings

- `HOSTNAME` - The website's hostname.

#### OlPosthog app settings

All settings for the `mitol-django-olposthog` app are prefaced with 'POSTHOG'.

- `POSTHOG_ENABLED` - `True` in order to enable Posthog feature flags in the application.  `False` to disable Posthog feature flags.
- `POSTHOG_PROJECT_API_KEY` - Required if POSTHOG_ENABLED is True. Private API key to communicate with PostHog.
- `POSTHOG_API_HOST` - Required if POSTHOG_ENABLED is True. Host URL for the PostHog API.
- `POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS` - Timeout(MS) for PostHog feature flag requests.
- `POSTHOG_MAX_RETRIES` - Numbers of time requests to PostHog should be retried after failing.

#### Cache table creation
Add the following cache defintion to your `CACHES` in the settings.py file of your Django application.
```
CACHES = {
  "durable": {
      "BACKEND": "django.core.cache.backends.db.DatabaseCache",
      "LOCATION": "durable_cache",
  },
}
```

You must create the cache included in this library.  This can be done by running the following command from within the Django application that this library is being added to: `./manage.py createcachetable`.

### Usage

#### Check single feature flag value
You can check the value of a feature flag on Posthog with the following code:
```
from mitol.olposthog.features import is_enabled
is_enabled(<FEATURE_FLAG_NAME>)
```
This will return a boolean value based on whether the Posthog feature flag is True or False.

#### Retrieve all feature flags from Posthog
You can retrieve all the feature flags from Posthog using:
```
from mitol.olposthog.features import get_all_feature_flags
get_all_feature_flags()
```
