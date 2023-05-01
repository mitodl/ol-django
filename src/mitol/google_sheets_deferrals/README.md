mitol-django-google-sheets-deferrals
---

This is the Open Learning Django Google Sheets library for handling deferral requests over Google Sheets
### Setup
`pip install mitol-django-google-sheets-deferrals`

Add the google sheets app:

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets_deferrals.apps.GoogleSheetsDeferralsApp",
]
```

### Configuration

#### Gather Values


1. The IDs of the deferral and deferral sheets in the change of enrollment spreadsheet. These can
    be found by opening the spreadsheet, selecting the "Refunds" or "Deferrals" worksheets, and
    copying down the `gid` value in the URL.
    
    Example: 
      > `https://docs.google.com/spreadsheets/d/abcd1234efgh5678bQFCQ7SSFBH5xHip0Gx2wPKT4fUA/edit#gid=THIS_IS_THE_WORKSHEET_ID`
1. The index of the first row where form-driven data begins in the deferral worksheet.
    If you're starting with no data already filled in these sheets (recommended), just use the index
    of the first non-header row. Use the row index exactly as it appears in the spreadsheet.


Set the following:

- `MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID`
  > ID of the worksheet within the deferral change request spreadsheet that contains enrollment deferral requests from step 2

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

# settings.py

MITOL_GOOGLE_SHEETS_DEFERRAL_PLUGINS = [
    "ecommerce.plugins.DeferralPlugin"
]

# ecommerce/plugins.py
```python
from mitol.google_sheets_deferral import hookimpl

class DeferralPlugin:
    @hookimpl
    def deferral_process_request(deferral_request: DeferralRequestRow) -> DeferralResult:
        # TODO: look up the user/enrollment
        # TODO: unenroll user from and enroll to
```
### Usage
Processing deferrals
```python
deferral_request_handler = DeferralRequestHandler()
results = deferral_request_handler.process_sheet()
```