### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps:


- [`mitol-django-mail`](mitol-django-mail/) - Mail app and APIs


### Navigating this repository

Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name. Within the apps, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`, with module paths following the pattern `mitol.{name}`, with the app itself being adding to `INSTALLED_APPS` as `"{name}"`.

Within each directory there is also a `testapp` directory that contains a full django app that tests integration of the reusable app. This app also functions as an example of how to use the app.

#### Adding a new app

- Create the project: `django-admin startproject mitol-django-$NAME && cd mitol-django-$NAME`
- Move the default app aside to use as the testapp: `mv mitol-django-$NAME testapp`
- Initialize poetry project: `poetry init`
- Create the reuseable app:
  - `mkdir mitol`
  - `./manage.py startapp $NAME`
  - `mv $NAME mitol/`
