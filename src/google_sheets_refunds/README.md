mitol-django-google-sheets-refunds
---

This is the Open Learning Django Google Sheets library for handling refund requests over Google Sheets
### Setup
Before you begin setting up this library make sure you set up `mitol-django-google-sheets` first. Follow the instructions [here](https://github.com/mitodl/ol-django/blob/85bea3ec5da01180ef943deb89b14d1463eb7c21/src/mitol/google_sheets/README.md).

Once you have `mitol-django-google-sheets` installed, then:

`pip install mitol-django-google-sheets-refunds`

#### In `settings.py`

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets_refunds.apps.GoogleSheetsRefundsApp",
]
```


```python
MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = [
    "ecommerce.plugins.RefundPlugin"
]
```

#### In `ecommerce/plugins.py`
```python
from mitol.google_sheets_refunds.hooks import hookimpl

class RefundPlugin:
    @hookimpl
    def refunds_process_request(refund_request: RefundRequestRow) -> RefundResult:
        # TODO: look up the user/order
        # TODO: mark the order as refunded
        # TODO: unenroll the user
```

#### Create your google sheets folder
The structure of the folder should look as the following:

1. Spreadsheet that contains sheets with 'Refund Form Responses' and the 'Refunds' sheets, that is being processed.
2. Request Form

Ask a developer for a template folder to copy this structure.


#### Add settings to your app

Set `MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID` in your .env file. It is required.

Some settings have default values, which you might need to update, if your sheet is different.

Description of settings (in addition to the ones described in `mitol-django-google-sheets`):

- `MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID`
  > The IDs of the refund and deferral sheets in the change of enrollment spreadsheet. These can
    be found by opening the spreadsheet, selecting the "Refunds" or "Deferrals" worksheets, and
    copying down the `gid` value in the URL.
    
    Example:
    `https://docs.google.com/spreadsheets/d/<MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID>/edit#gid=<MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID>`


- `MITOL_GOOGLE_SHEETS_REFUNDS_PROCESSOR_COL` 
  > The zero-based index of the refund change sheet column that contains the user that processed the row

- `MITOL_GOOGLE_SHEETS_REFUNDS_COMPLETED_DATE_COL`
  > The zero-based index of the refund change sheet column that contains the row completion date

- `MITOL_GOOGLE_SHEETS_REFUNDS_ERROR_COL`
  > The zero-based index of the refund change sheet column that contains row processing error messages

- `MITOL_GOOGLE_SHEETS_REFUNDS_SKIP_ROW_COL`
  > The zero-based index of the refund change sheet column that indicates whether the row should be skipped

- `MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW`
  > The first row (as it appears in the spreadsheet) of data that our scripts should consider processing in the refund request spreadsheet


### Usage
To processing your google sheet with refund requests simply add:
```python
refund_request_handler = RefundRequestHandler()
results = refund_request_handler.process_sheet()
```


Here are two main ways that we are currently getting our Google Sheets Refunds processed:

1. Run a management command. For example:
`./manage.py process_refund_requests -i "<spreadsheet id>"`
2. Set up a scheduled celery task. For example:
```python
from mitol.google_sheets_refunds.api import RefundRequestHandler
from main.celery import app

@app.task
def process_refund_requests():
    """
    Task to process refund requests from Google sheets
    """
    refund_request_handler = RefundRequestHandler()
    if not refund_request_handler.is_configured():
        log.warning("MITOL_GOOGLE_SHEETS_* are not set")
        return
    refund_request_handler.process_sheet()
```

### Develper setup
For local development setup and testing please follow the instructions `Developer Setup` [here](https://github.com/mitodl/ol-django/blob/85bea3ec5da01180ef943deb89b14d1463eb7c21/src/mitol/google_sheets/README.md#developer-setup).