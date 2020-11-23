`mitol-django-digital-credentials` test app
---

#### Setup

To run this app in local development mode, copy `testapp/settings/example.dev.py` to  `testapp/settings/dev.py`. This file has the same defaults as `testapp/settings/test.py`, but it is gitignored so you can safely add secrets to it. `manage.py` and `testapp/wsgi.py` both load `dev.py`.

#### Usage

Ensure the [`sign-and-verify`](https://github.com/digitalcredentials/sign-and-verify) service is running locally.

In the `mitol-django-digital-credentials directory`, you can test this app out by running:

- `poetry run python manage.py migrate` - migrates sqlite db (gitignored)
- `poetry run python manage.py runserver`
- `poetry run python manage.py shell`:

```python
import json
import requests
from datetime import timedelta
from oauth2_provider.models import AccessToken, get_application_model
from django.contrib.auth.models import User
from mitol.common.utils import now_in_utc
from testapp.factories import DemoCoursewareDigitalCredentialRequestFactory

Application = get_application_model()

### Create a user
learner, _ = User.objects.get_or_create(
  username="myuser",
  defaults=dict(email="myuser@example.com")
)

# create oauth2 app and access token
application, _ = Application.objects.get_or_create(
    name="Test Application",
    defaults=dict(
      redirect_uris="http://localhost",
      user=learner,
      client_type=Application.CLIENT_CONFIDENTIAL,
      authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )
)
access_token, _ = AccessToken.objects.update_or_create(
    user=learner,
    token="1234567890",
    application=application,
    defaults=dict(
      expires=now_in_utc() + timedelta(days=1),
      scope="read write digitalcredentials",
    )
)

request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

did = "did:example:456"
response = requests.post(
  "http://localhost:5000/generate/controlproof",
  json={
    "presentationId": did,
    "holder": "did:web:digitalcredentials.github.io",
    "verificationMethod": "did:web:digitalcredentials.github.io#96K4BSIWAkhcclKssb8yTWMQSz4QzPWBy-JsAFlwoIs",
    "challenge": str(request.uuid)
  }
)
data = json.dumps(response.json())
print(f"""curl \
  -H 'Authorization: Bearer {access_token.token}' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  --data '{data}' \
  http://localhost:8000/api/credentials/request/{request.uuid}/""")
```

- Copy/paste and run curl command printed above
