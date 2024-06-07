mitol-django-mail
---

This is the Open Learning Django Mail app. It provides a few key features around mail:

- Templated multipart html emails
- Automatic generation of plaintext portion of multipart email
- CSS inlining for email html


### Getting started

`pip install mitol-django-mail`

Add the mail app:

```python
INSTALLED_APPS = [
    ...
    "mitol.mail.apps.MailApp",
]
```

### Settings

#### Common Django settings

- `SITE_BASE_URL` - the website's host url, including the protocol (e.g. "https://example.com/")
- `SITE_NAME` - the website's name

#### Mail app settings

All settings for the `mitol-django-mail` app are namespaced in django settings with `MITOL_MAIL_` prefix.

- `MITOL_MAIL_FROM_EMAIL` - the default from email for all messages
- `MITOL_MAIL_REPLY_TO_ADDRESS` - the default reply-to email for all messages
- `MITOL_MAIL_MESSAGE_CLASSES` - a list of fully qualified message class names that make the message classes available in the debugger
- `MITOL_MAIL_ENABLE_EMAIL_DEBUGGER` - `True` if the email debugger should be enabled, you probably want to set this to the same value as `DEBUG`
- `MITOL_MAIL_RECIPIENT_OVERRIDE` - only used locally, this overrides the recipient of all outgoing email messages
- `MITOL_MAIL_FORMAT_RECIPIENT_FUNC` - (optional) set to a custom function to format recipients. You'll typically use this if you're storing the name in a place other that Django's builtin `User` model. Default: `"mitol.mail.defaults.format_recipient"`.
- `MITOL_MAIL_CAN_EMAIL_USER_FUNC` - (optional) set to a custom function to determine whether a user can be sent an email. You'll typically use this if you have additional criteria beyond the user having an email. Default: `"mitol.mail.defaults.can_email_user"`.
- `MITOL_MAIL_CONNECTION_BACKEND` - the connection backend to use for email sending. You'd use this only if you're doing something really custom that `anymail` doesn't give you. Default: `"anymail.backends.mailgun.EmailBackend"`.

### Usage

#### Create message classes

This involves subclassing `mitol.mail.messages.TemplatedMessage`. To subclass, do the following:

- `template_name` attribute - `str` that denotes the directory within `templates/mail` that this message's templates reside in (e.g. `"password_reset"`)
- `name` attribute - a human-friendly name for your message (e.g. `"Password Reset"`)
- `get_debug_template_context` - static method that returns a context dict for rendering the email in the debugger


#### Define templates
In your apps's `templates` directory, create some templates:
```
templates/
  mail/
    {template_name}/
      subject.txt
      body.html
```

#### Configure settings.py

Add your custom message class to `MITOL_MAIL_MESSAGE_CLASSES` so it is available in the debugger.

#### Optional customizations

Optionally, you can also override:

- `get_base_template_context` - extend the default base template context used with all emails of this type. Return type is a `dict`. As a best practice you should be merging with `super().get_base_template_context()`.
- `get_default_headers` - extend the default headers included with all emails of this type. Return type is a `dict`. As a best practice you should be merging with `super().get_default_headers()`.
