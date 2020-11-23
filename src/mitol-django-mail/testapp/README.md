`mitol-django-mail` test app
---

#### Setup

To run this app in local development mode, copy `testapp/settings/example.dev.py` to  `testapp/settings/dev.py`. This file has the same defaults as `testapp/settings/test.py`, but it is gitignored so you can safely add secrets to it. `manage.py` and `testapp/wsgi.py` both load `dev.py`.

#### Usage

In the `mitol-django-mail directory`, you can test this app out by running:

- `poetry run python manage.py migrate` - migrates sqlite db (gitignored)
- `poetry run python manage.py shell`:

```python
### Create a user
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.create(username="<my-username>", email="<my-email>")
```
```python
### Send an email
from mitol.mail.api import get_message_sender
from mitol.mail.messages import TemplatedMessage
from testapp.messages import SampleMessage
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username="<my-username>")
with get_message_sender(SampleMessage, shared_context={}) as sender:
    sender.build_and_send_message(user, {})
```
