"""API with general functionality for all enrollment change spreadsheets"""
import json
import logging
import operator as op

from django.conf import settings
from django.db import transaction
from django.utils.functional import cached_property

from mitol.common.utils.collections import group_into_dict
from mitol.common.utils.config import get_missing_settings
from mitol.google_sheets.api import get_authorized_pygsheets_client
from mitol.google_sheets.constants import (
    GOOGLE_SHEET_FIRST_ROW,
    REQUIRED_GOOGLE_SHEETS_CLIENT_SETTINGS,
    REQUIRED_GOOGLE_SHEETS_SERVICE_ACCOUNT_SETTINGS,
    REQUIRED_GOOGLE_SHEETS_SETTINGS,
)
from mitol.google_sheets.utils import (
    ResultType,
    RowResult,
    format_datetime_for_sheet_formula,
    get_data_rows,
    get_data_rows_after_start,
)

log = logging.getLogger(__name__)


class SheetHandler:
    """
    Base class for managing the processing of a spreadsheet which contains requests for work to be done
    (creating enrollment codes, changing enrollments, etc.).
    """

    pygsheets_client = None
    spreadsheet = None
    sheet_metadata = None

    def is_configured(self):
        """
        Checks for required settings.

        Returns:
            bool: false if required settings are missing
        """
        is_configured = True
        missing = get_missing_settings(REQUIRED_GOOGLE_SHEETS_SETTINGS)

        for variable in missing:
            log.warning("Google sheets setting %s is not set.", variable)
            is_configured = False

        missing_service_account_settings = get_missing_settings(
            REQUIRED_GOOGLE_SHEETS_SERVICE_ACCOUNT_SETTINGS
        )
        missing_client_settings = get_missing_settings(
            REQUIRED_GOOGLE_SHEETS_CLIENT_SETTINGS
        )
        missing_mutually_exclusive_settings = [
            missing_service_account_settings,
            missing_client_settings,
        ]

        if not any(missing_mutually_exclusive_settings):
            # if no settings are missing, both are configured
            log.error(
                "Google sheets is configured for both service account and client credentials"
            )
            is_configured = False
        elif all(missing_mutually_exclusive_settings):
            # if all the settings are missing, nothing is configured
            log.error("Google sheets is not configured with credentials")
            is_configured = False
        elif (
            0
            < len(missing_client_settings)
            < len(REQUIRED_GOOGLE_SHEETS_CLIENT_SETTINGS)
        ):
            for variable in missing_client_settings:
                log.error("Google sheets setting %s is not set.", variable)
            is_configured = False

        # Note: there's no `else` clause here for service accounts
        # because there's only one setting for service accounts,
        # so this ends up being ambiguous with nothing being configured

        return is_configured

    @cached_property
    def worksheet(self):
        """
        Returns the correct Worksheet object for this spreadsheet

        Returns:
             pygsheets.worksheet.Worksheet: The Worksheet object
        """
        # By default, the first worksheet of the spreadsheet should be used
        return self.spreadsheet.sheet1

    def get_enumerated_rows(self):
        """
        Yields enumerated data rows of a spreadsheet (excluding header row(s)).

        Yields:
            Tuple[int, List[str]]: Row index (according to the Google Sheet, NOT zero-indexed) paired with the list
                of strings representing the data in each column of the row
        """
        yield from enumerate(
            get_data_rows(self.worksheet, include_trailing_empty=False),
            start=GOOGLE_SHEET_FIRST_ROW + 1,
        )

    def update_completed_rows(self, success_row_results):
        """
        Updates rows in the spreadsheet that were successfully processed.

        Args:
            success_row_results (Iterable[RowResult]): Objects representing the results of processing a row
        """
        raise NotImplementedError

    def update_row_errors(self, failed_row_results):
        """
        Updates rows in the spreadsheet that failed during processing.

        Args:
            failed_row_results (Iterable[RowResult]): Objects representing the results of processing a row
        """
        for row_result in failed_row_results:
            self.worksheet.update_value(
                "{}{}".format(
                    self.sheet_metadata.ERROR_COL_LETTER, row_result.row_index
                ),
                row_result.message,
            )

    def update_sheet_from_results(self, grouped_row_results):
        """
        Updates the relevant spreadsheet cells based on the row results and logs any necessary messages.

        Args:
            grouped_row_results (Dict[str, Iterable[RowResult]]): Objects representing the results of processing rows
                grouped by result type (success, failed, etc.)
        """
        processed_row_results = grouped_row_results.get(ResultType.PROCESSED, [])
        if processed_row_results:
            self.update_completed_rows(processed_row_results)
            log.warning(
                "Successfully processed rows in %s (%s): %s",
                self.sheet_metadata.sheet_name,
                self.sheet_metadata.worksheet_name,
                [row_result.row_index for row_result in processed_row_results],
            )
        failed_row_results = grouped_row_results.get(ResultType.FAILED, [])
        if failed_row_results:
            self.update_row_errors(failed_row_results)
            log.warning(
                "Processed rows with errors in %s (%s): %s",
                self.sheet_metadata.sheet_name,
                self.sheet_metadata.worksheet_name,
                [row_result.row_index for row_result in failed_row_results],
            )
        out_of_sync_row_results = grouped_row_results.get(ResultType.OUT_OF_SYNC, [])
        if out_of_sync_row_results:
            log.warning(
                "Rows found without a completed date, but local records indicate that they were completed: %s",
                [row_result.row_index for row_result in out_of_sync_row_results],
            )
            self.update_completed_rows(out_of_sync_row_results)
        ignored_row_results = grouped_row_results.get(ResultType.IGNORED, [])
        if ignored_row_results:
            log.warning(
                "Ignored rows in %s (%s): %s",
                self.sheet_metadata.sheet_name,
                self.sheet_metadata.worksheet_name,
                [row_result.row_index for row_result in ignored_row_results],
            )

    def post_process_results(self, grouped_row_results):
        """
        Helper method for executing any logic after the sheet processing results have been handled

        Args:
            grouped_row_results (Dict[str, Iterable[RowResult]]): Objects representing the results of processing rows
                grouped by result type (success, failed, etc.)
        """
        return grouped_row_results

    def get_or_create_request(self, row_data):
        """
        Ensures that an object exists in the database that represents this spreadsheet row, and
        that it reflects the correct state based on the raw data.

        Args:
            row_data (List[str]): Raw data from a row in the spreadsheet

        Returns:
            Tuple[Type(GoogleSheetsRequestModel), bool, bool]: A tuple containing an object representing the
                request, a flag that indicates whether or not it was newly created, and a flag that indicates
                whether or not it was updated.
        """
        raise NotImplementedError

    @staticmethod
    def validate_sheet(enumerated_rows):
        """
        Checks the request sheet data for any data issues beyond the scope of a single row (i.e.: any row data
        that is invalid because of the data in other rows in the sheet), and returns the valid rows paired
        with row results for the invalid rows. By default, all rows are considered valid.

        Args:
            enumerated_rows (Iterable[Tuple[int, List[str]]]): Row indices paired with a list of strings
                representing the data in each row

        Returns:
            Tuple[ Iterable[Tuple[int, List[str]]], List[RowResult] ]: Enumerated data rows with invalidated rows
                filtered out, paired with objects representing the rows that failed validation.
        """
        return enumerated_rows, []

    def filter_ignored_rows(self, enumerated_rows):
        """
        Takes an iterable of enumerated rows, and returns an iterable of those rows without the ones that should be
        ignored. By default, no rows are filtered.

        Args:
            enumerated_rows (Iterable[Tuple[int, List[str]]]): Row indices paired with a list of strings
                representing the data in each row

        Returns:
            Iterable[Tuple[int, List[str]]]: Iterable of data rows without the ones that should be ignored.
        """
        return enumerated_rows

    def process_row(self, row_index, row_data):
        """
        Ensures that the given spreadsheet row is correctly represented in the database,
        attempts to parse it, performs the necessary logic to service the request (e.g.: create enrollment codes),
        and returns the result of processing the row.

        Args:
            row_index (int): The row index according to the spreadsheet
            row_data (List[str]): The raw data of the given spreadsheet row

        Returns:
            Optional[RowResult]: An object representing the results of processing the row, or None if
                nothing needs to be done with this row.
        """
        raise NotImplementedError

    def process_sheet(self, limit_row_index=None):
        """
        Ensures that all non-legacy rows in the spreadsheet are correctly represented in the database,
        changes enrollments if appropriate, updates the spreadsheet to reflect any changes
        made, and returns a summary of those changes.

        Returns:
            dict: A summary of the changes made while processing the enrollment change request sheet
        """
        if limit_row_index is None:
            enumerated_rows = self.get_enumerated_rows()
        else:
            enumerated_rows = [
                (limit_row_index, self.worksheet.get_row(limit_row_index))
            ]
        filtered_rows = self.filter_ignored_rows(enumerated_rows)
        valid_enumerated_rows, row_results = self.validate_sheet(filtered_rows)
        for row_index, row_data in valid_enumerated_rows:
            row_result = None
            try:
                row_result = self.process_row(row_index, row_data)
            except Exception as exc:
                log.exception("Error processing row %s from google sheets", row_index)
                row_result = RowResult(
                    row_index=row_index,
                    row_db_record=None,
                    row_object=None,
                    result_type=ResultType.FAILED,
                    message="Error: {}".format(str(exc)),
                )
            finally:
                if row_result:
                    row_results.append(row_result)
        if not row_results:
            return {}
        grouped_row_results = group_into_dict(
            row_results, key_fn=op.attrgetter("result_type")
        )
        self.update_sheet_from_results(grouped_row_results)
        self.post_process_results(grouped_row_results)
        return {
            result_type.value: [row_result.row_index for row_result in row_results]
            for result_type, row_results in grouped_row_results.items()
        }


class GoogleSheetsChangeRequestHandler(SheetHandler):
    """
    Base class for managing the processing of enrollment change requests from a spreadsheet
    """

    def __init__(
        self, spreadsheet_id, worksheet_id, start_row, sheet_metadata, request_model_cls
    ):
        """

        Args:
            spreadsheet_id (int):
            worksheet_id (int):
            start_row (int):
            sheet_metadata (Type(SheetConfig)):
            request_model_cls (Type(GoogleSheetsRequestModel)):
        """
        self.pygsheets_client = get_authorized_pygsheets_client()
        self.spreadsheet = self.pygsheets_client.open_by_key(spreadsheet_id)
        self.worksheet_id = worksheet_id
        self.start_row = start_row
        self.sheet_metadata = sheet_metadata
        self.request_model_cls = request_model_cls

    @cached_property
    def worksheet(self):
        return self.spreadsheet.worksheet("id", value=self.worksheet_id)

    def get_enumerated_rows(self):
        # Only yield rows in the spreadsheet that come after the legacy rows
        # (i.e.: the rows of data that were manually entered before we started automating this process)
        row_count = len(self.worksheet.get_all_values(include_tailing_empty_rows=False))
        first_row_to_process = self.start_row
        if int(settings.MITOL_GOOGLE_SHEETS_PROCESS_ONLY_LAST_ROWS_NUM) > 0:
            # allow to choose to process only last few rows
            new_first_row = (
                row_count
                - int(settings.MITOL_GOOGLE_SHEETS_PROCESS_ONLY_LAST_ROWS_NUM)
                + 1
            )
            first_row_to_process = (
                new_first_row if new_first_row > self.start_row else self.start_row
            )
        logging.warning(
            "Going to process the sheet starting with row %s", first_row_to_process
        )
        return enumerate(
            get_data_rows_after_start(
                self.worksheet,
                start_row=first_row_to_process,
                start_col=1,
                end_col=self.sheet_metadata.num_columns,
            ),
            start=first_row_to_process,
        )

    def update_completed_rows(self, success_row_results):
        for row_result in success_row_results:
            self.worksheet.update_values(
                crange="{processor_col}{row_index}:{error_col}{row_index}".format(
                    processor_col=self.sheet_metadata.PROCESSOR_COL_LETTER,
                    error_col=self.sheet_metadata.ERROR_COL_LETTER,
                    row_index=row_result.row_index,
                ),
                values=[
                    [
                        settings.MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME,
                        format_datetime_for_sheet_formula(
                            row_result.row_db_record.date_completed.astimezone(
                                settings.MITOL_GOOGLE_SHEETS_DATE_TIMEZONE
                            )
                        ),
                        "",
                    ]
                ],
            )

    def get_or_create_request(self, row_data):
        form_response_id = int(
            row_data[self.sheet_metadata.FORM_RESPONSE_ID_COL].strip()
        )
        user_input_json = json.dumps(
            self.sheet_metadata.get_form_input_columns(row_data)
        )
        with transaction.atomic():
            (
                enroll_change_request,
                created,
            ) = self.request_model_cls.objects.select_for_update().get_or_create(
                form_response_id=form_response_id,
                defaults=dict(raw_data=user_input_json),
            )
            raw_data_changed = enroll_change_request.raw_data != user_input_json
            if raw_data_changed:
                enroll_change_request.raw_data = user_input_json
                enroll_change_request.save()
        return enroll_change_request, created, raw_data_changed

    def process_row(self, row_index, row_data):
        raise NotImplementedError
