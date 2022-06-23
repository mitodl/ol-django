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
First, gather a bunch of ID-type values from Drive:

1. The "Client ID" and "Client secret" values for the web application credentials you created
    above ([API Console Credentials section](https://console.developers.google.com/apis/credentials))
2. Your API project ID, which you can find in Google Cloud Platform > IAM & Admin > Settings > Project ID.
    Example: `my-api-project-1234567890123`

Now using the values you have gathered set those settings:
- `MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS` - The contents of the Service Account credentials JSON to use for Google API auth
- `MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID` - Client ID from Google API credentials
- `MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET` - Client secret from Google API credentials
- `MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID` - ID for the Google API project where the credentials were created
- `MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID` - ID of the Shared Drive (a.k.a. Team Drive). This is equal to the top-level folder ID


### Usage

In production, webhooks (also known as "file watches") are set up to make a request
to your app, so that new changes to spreadsheets can be automatically processed. You can set
those up locally too, but it's probably easier just to use the management commands.

Here's an example workflow for making a request for refunds:

1. Fill out and submit the spreadsheet request form. This should add a row to the
 first worksheet in the enrollment code request spreadsheet.
2. Run the management command to process the sheet:
 `./manage.py process_refund_requests -i "<spreadsheet id>"`. This should
 update the "Date Processed" column for the row you added.
3. Check the status of the request in the spreadsheet.


### Integration with mitol-google-sheets

Add this to your settings file:
```python
# import_settings_module, imports the default settings defined in mitol-google-sheets app
from mitol.common.envs import import_settings_modules
import_settings_modules(globals(), "mitol.google-sheets.settings.google_sheets")
```

Create spreadsheed config, for example:
```python
from mitol.google_sheets.utils import SingletonSheetConfig
class RefundRequestSheetConfig(SingletonSheetConfig, subclass_type=<type_of_spreadsheet>):
    """Metadata for the refund request spreadsheet"""
    def __init__(self):
        self.sheet_type = "<type_of_spreadsheet>"
        self.sheet_name = "Refund Request sheet"
        self.worksheet_type = WORKSHEET_TYPE_REFUND
        self.worksheet_name = "Refunds"
```
Subclassing `SingletonSheetConfig` will allow you have your spreadsheet type registered in the base class. This
allows to determine the appropriate config class based on the type of spreadsheet
by running `SingletonSheetConfig.get_subclass_by_type(<type_of_sheet>)`. This is used in various
tasks, and management commands where you want to set up file watch on all current registered
spreadsheets.

In your `urls.py`:
```python
urlpatterns = (
    [
        ...
        path("", include("mitol.google_sheets.urls")),
    ]
)
```
