`mitol-django-authentication` test app
---

#### Setup

To run this app in local development mode, copy `testapp/settings/example.dev.py` to  `testapp/settings/dev.py`. This file has the same defaults as `testapp/settings/test.py`, but it is gitignored so you can safely add secrets to it. `manage.py` and `testapp/wsgi.py` both load `dev.py`.

#### Usage

In the `mitol-django-authentication` directory, you can test this app out by running:

- `poetry run python manage.py migrate` - migrates sqlite db (gitignored)
- `poetry run python manage.py shell`:


```python
### Create a user
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.create(username="<my-username>", email="<my-email>")
```
- `poetry run python manage.py runserver` - run the django `testapp` locally at http://localhost:8000/
