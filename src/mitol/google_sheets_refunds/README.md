mitol-django-google-sheets-refunds
---

This is the Open Learning Django Google Sheets library for handling refund requests over Google Sheets
### Setup
`pip install mitol-django-google-sheets-refunds`

Add the google sheets refunds app:

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets_refunds.apps.GoogleSheetsRefundsApp",
]
```

### Configuration

#### Gather Values


1. The IDs of the refund and deferral sheets in the change of enrollment spreadsheet. These can
    be found by opening the spreadsheet, selecting the "Refunds" or "Deferrals" worksheets, and
    copying down the `gid` value in the URL.
    
    Example: 
      > `https://docs.google.com/spreadsheets/d/abcd1234efgh5678bQFCQ7SSFBH5xHip0Gx2wPKT4fUA/edit#gid=THIS_IS_THE_WORKSHEET_ID`
1. The index of the first row where form-driven data begins in the refund worksheet.
    If you're starting with no data already filled in these sheets (recommended), just use the index
    of the first non-header row. Use the row index exactly as it appears in the spreadsheet.


Set the following:

- `MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID`
  > ID of the worksheet within the refund change request spreadsheet that contains enrollment refund requests from step 2

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

# settings.py

MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = [
    "ecommerce.plugins.RefundPlugin"
]

# ecommerce/plugins.py
```python
from mitol.google_sheets_refunds import hookimpl

class RefundPlugin:
    @hookimpl
    def refunds_process_request(refund_request: RefundRequestRow) -> RefundResult:
        # TODO: look up the user/order
        # TODO: mark the order as refunded
        # TODO: unenroll the user
```
### Usage
Processing refunds
```python
refund_request_handler = RefundRequestHandler()
results = refund_request_handler.process_sheet()
```