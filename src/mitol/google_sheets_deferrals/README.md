mitol-django-google-sheets-deferrals
---

This is the Open Learning Django Google Sheets library for handling deferral requests over Google Sheets
### Setup
Before you begin setting up this library make sure you set up `mitol-django-google-sheets` first. Follow the instructions [here](https://github.com/mitodl/ol-django/blob/85bea3ec5da01180ef943deb89b14d1463eb7c21/src/mitol/google_sheets/README.md).

Once you have `mitol-django-google-sheets` installed, then:

`pip install mitol-django-google-sheets-deferrals`

#### In `settings.py`

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets_deferrals.apps.GoogleSheetsDeferralsApp",
]
```


```python
MITOL_GOOGLE_SHEETS_DEFERRALS_PLUGINS = [
    "ecommerce.plugins.DeferralPlugin"
]
```

#### In `ecommerce/plugins.py`
```python
from mitol.google_sheets_deferrals.hooks import hookimpl

class DeferralPlugin:
    @hookimpl
    def deferrals_process_request(deferral_request: DeferralRequestRow) -> DeferralResult:
        # TODO: look up the user/enrollment
        # TODO: unenroll user from and enroll to
```

#### Create your google sheets folder
The structure of the folder should look as the following:

1. Spreadsheet that contains sheets with 'Deferral Form Responses' and the 'Deferrals' sheets, that is being processed.
2. Request Form

Ask a developer for a template folder to copy this structure.


#### Add settings to your app

Set `MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID` in your .env file. It is required.

Some settings have default values, which you might need to update, if your sheet is different.

Description of settings (in addition to the ones described in `mitol-django-google-sheets`):

- `MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID`
  > The IDs of the refund and deferral sheets in the change of enrollment spreadsheet. These can
    be found by opening the spreadsheet, selecting the "Refunds" or "Deferrals" worksheets, and
    copying down the `gid` value in the URL.
    
    Example:
    `https://docs.google.com/spreadsheets/d/<MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID>/edit#gid=<MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID>`


- `MITOL_GOOGLE_SHEETS_DEFERRALS_PROCESSOR_COL` 
  > The zero-based index of the deferral change sheet column that contains the user that processed the row

- `MITOL_GOOGLE_SHEETS_DEFERRALS_COMPLETED_DATE_COL`
  > The zero-based index of the deferral change sheet column that contains the row completion date

- `MITOL_GOOGLE_SHEETS_DEFERRALS_ERROR_COL`
  > The zero-based index of the deferral change sheet column that contains row processing error messages

- `MITOL_GOOGLE_SHEETS_DEFERRALS_SKIP_ROW_COL`
  > The zero-based index of the deferral change sheet column that indicates whether the row should be skipped

- `MITOL_GOOGLE_SHEETS_DEFERRALS_FIRST_ROW`
  > The first row (as it appears in the spreadsheet) of data that our scripts should consider processing in the deferral request spreadsheet


### Usage
To processing your google sheet with deferral requests simply add:
```python
deferral_request_handler = DeferralRequestHandler()
results = deferral_request_handler.process_sheet()
```


Here are two main ways that we are currently getting our Google Sheets Deferrals processed:

1. Run a management command. For example:
`./manage.py process_deferral_requests -i "<spreadsheet id>"`
2. Set up a scheduled celery task. For example:
```python
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from main.celery import app

@app.task
def process_deferral_requests():
    """
    Task to process deferral requests from Google sheets
    """
    deferral_request_handler = DeferralRequestHandler()
    if not deferral_request_handler.is_configured():
        log.warning("MITOL_GOOGLE_SHEETS_* are not set")
        return
    deferral_request_handler.process_sheet()
```

### Develper setup
For local development setup and testing please follow the instructions `Developer Setup` [here](https://github.com/mitodl/ol-django/blob/85bea3ec5da01180ef943deb89b14d1463eb7c21/src/mitol/google_sheets/README.md#developer-setup).