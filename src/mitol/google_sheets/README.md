mitol-django-google-sheets
---

This is the Open Learning Django Google Sheets core library. The purpose of it is to wrap core functionality around Google Sheets for consumption in more feature specific libraries.

### Setup

`pip install mitol-django-core`

Add the google sheets app:

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets.apps.GoogleSheetsApp",
]
```

### Configuration

- `MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS` - set to the fully qualified path for a user model factory, otherwise a default based on `django.contrib.auth.models.User` is used
- `MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID` - Client ID from Google API credentials
- `MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET` - Client secret from Google API credentials
- `MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID` - ID for the Google API project where the credentials were created
- `MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID` - ID of the Shared Drive (a.k.a. Team Drive). This is equal to the top-level folder ID


### Use

TODO