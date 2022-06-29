mitol-django-google-sheets-refunds
---

This is the Open Learning Django Google Sheets library for handling refund requests over Google Sheets
### Setup
Set the following:
`MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID` - ID of the worksheet within the enrollment change request spreadsheet that contains enrollment refund requests
`MITOL_GOOGLE_SHEETS_REFUNDS_PROCESSOR_COL` - The zero-based index of the enrollment change sheet column that contains the user that processed the row
`MITOL_GOOGLE_SHEETS_REFUNDS_COMPLETED_DATE_COL` - The zero-based index of the enrollment change sheet column that contains the row completion date
`MITOL_GOOGLE_SHEETS_REFUNDS_ERROR_COL` -
        "The zero-based index of the enrollment change sheet column that contains row processing error messages
  
`MITOL_GOOGLE_SHEETS_REFUNDS_SKIP_ROW_COL` - The zero-based index of the enrollment change sheet column that indicates whether the row should be skipped
`MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW` - The first row (as it appears in the spreadsheet) of data that our scripts should consider processing in the refund request spreadsheet

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