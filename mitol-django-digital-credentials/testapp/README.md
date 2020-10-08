`mitol-django-digital-credentials` test app
---

#### Setup

To run this app in local development mode, copy `testapp/settings/example.dev.py` to  `testapp/settings/dev.py`. This file has the same defaults as `testapp/settings/test.py`, but it is gitignored so you can safely add secrets to it. `manage.py` and `testapp/wsgi.py` both load `dev.py`.

#### Usage

Ensure the [`sign-and-verify`](https://github.com/digitalcredentials/sign-and-verify) service is running locally.

In the `mitol-django-digital-credentials directory`, you can test this app out by running:

- `poetry run python manage.py migrate` - migrates sqlite db (gitignored)
- `poetry run python manage.py shell`:

```python
from datetime import timedelta
from oauth2_provider.models import AccessToken, get_application_model
from mitol.common.factories import UserFactory
from mitol.common.utils import now_in_utc
from testapp.factories import DemoCoursewareDigitalCredentialRequestFactory

Application = get_application_model()

### Create a user
learner = UserFactory.create()

# create oauth2 app and access token
application = Application.objects.create(
    name="Test Application",
    redirect_uris="http://localhost",
    user=learner,
    client_type=Application.CLIENT_CONFIDENTIAL,
    authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
)
access_token = AccessToken.objects.create(
    user=learner,
    token="1234567890",
    application=application,
    expires=now_in_utc() + timedelta(days=1),
    scope="read write digitalcredentials",
)

request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

print(f"export ACCESS_TOKEN={access_token.token}")
print(f"export UUID={request.uuid}")
```

- Copy/paste and run the exports printed above
- `poetry run python manage.py runserver`

- Run a test request:

```
curl \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  --data '{"learnerDid": "did:example:123"}'\
  http://localhost:8000/api/credentials/request/$UUID/
```
