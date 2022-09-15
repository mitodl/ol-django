"""API for the Sheets app"""
import datetime
import json
import logging
import os
import pickle
from collections import namedtuple
from urllib.parse import urljoin

import pygsheets
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

from mitol.common.utils import now_in_utc
from mitol.google_sheets.constants import (
    DEFAULT_GOOGLE_EXPIRE_TIMEDELTA,
    GOOGLE_API_FILE_WATCH_KIND,
    GOOGLE_API_NOTIFICATION_TYPE,
    GOOGLE_TOKEN_URI,
    REQUIRED_GOOGLE_API_SCOPES,
)
from mitol.google_sheets.models import GoogleApiAuth
from mitol.google_sheets.utils import format_datetime_for_google_timestamp

log = logging.getLogger(__name__)

DEV_TOKEN_PATH = "localdev/google.token"
FileWatchSpec = namedtuple(
    "FileWatchSpec",
    ["sheet_metadata", "sheet_file_id", "channel_id", "handler_url", "force"],
)


def get_google_creds_from_pickled_token_file(token_file_path):
    """
    Helper method to get valid credentials from a local token file (and refresh as necessary).
    For dev use only.
    """
    with open(token_file_path, "rb") as f:
        creds = pickle.loads(f.read())
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file_path, "wb") as token:
            pickle.dump(creds, token)
    if not creds:
        raise ImproperlyConfigured("Local token file credentials are empty")
    if not creds.valid:
        raise ImproperlyConfigured("Local token file credentials are invalid")
    return creds


def get_credentials():
    """
    Gets valid Google API client credentials

    Returns:
        google.oauth2.credentials.Credentials: Credentials to be used by the Google Drive client/pygsheets/etc.

    Raises:
        ImproperlyConfigured: Raised if no credentials have been configured
    """
    if settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS:
        is_sharing_to_service_account = any(
            email
            for email in settings.MITOL_GOOGLE_SHEETS_ADMIN_EMAILS
            if email.endswith(settings.MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN)
        )
        if not is_sharing_to_service_account:
            raise ImproperlyConfigured(
                "If Service Account auth is being used, the MITOL_GOOGLE_SHEETS_ADMIN_EMAILS setting must "
                "include a Service Account email for spreadsheet updates/creation to work. "
                "Add the Service Account email to that setting, or remove the MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS "
                "setting and use a different auth method."
            )
        return ServiceAccountCredentials.from_service_account_info(
            json.loads(settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS),
            scopes=REQUIRED_GOOGLE_API_SCOPES,
        )
    google_api_auth = GoogleApiAuth.objects.order_by("-updated_on").first()
    if google_api_auth:
        creds = Credentials(
            token=google_api_auth.access_token,
            refresh_token=google_api_auth.refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID,
            client_secret=settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET,
            scopes=REQUIRED_GOOGLE_API_SCOPES,
        )
        # Proactively refresh if necessary
        needs_refresh = (
            creds.expired
            if creds.expiry
            else google_api_auth.updated_on
            < (now_in_utc() - datetime.timedelta(**DEFAULT_GOOGLE_EXPIRE_TIMEDELTA))
        )
        if needs_refresh:
            log.info("Refreshing GoogleApiAuth credentials...")
            creds.refresh(Request())
            GoogleApiAuth.objects.filter(id=google_api_auth.id).update(
                access_token=creds.token, updated_on=now_in_utc()
            )
        return creds
    # (For local development use only) You can use a locally-created token for auth.
    # This token can be created by following the Google API Python quickstart guide:
    # https://developers.google.com/sheets/api/quickstart/python.
    # A script with more helpful options than the one in that guide can be found here:
    # https://gist.github.com/gsidebo/b87abaafda3e79186c1e5f7f964074ab
    if settings.ENVIRONMENT == "dev":
        token_file_path = os.path.join(settings.BASE_DIR, DEV_TOKEN_PATH)
        if os.path.exists(token_file_path):
            return get_google_creds_from_pickled_token_file(token_file_path)
    raise ImproperlyConfigured("Authorization with Google has not been completed.")


def get_authorized_pygsheets_client():
    """
    Instantiates a pygsheets Client and authorizes it with the proper credentials.

    Returns:
        pygsheets.client.Client: The authorized Client object
    """
    credentials = get_credentials()
    pygsheets_client = pygsheets.authorize(custom_credentials=credentials)
    if settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID:
        pygsheets_client.drive.enable_team_drive(
            team_drive_id=settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID
        )
    return pygsheets_client


class ExpandedSheetsClient:
    """
    Helper class that executes some Drive/Sheets API requests that pygsheets doesn't directly support
    """

    def __init__(self, pygsheets_client):
        """
        Args:
            pygsheets_client (pygsheets.client.Client): An authorized pygsheets client
        """
        self.pygsheets_client = pygsheets_client
        self.supports_team_drives = bool(settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID)

    def get_metadata_for_matching_files(self, query, file_fields="id, name"):
        """
        Fetches metadata for all Drive files that match a given query
        Args:
            query (str): The Drive files query (ref: https://developers.google.com/drive/api/v3/search-files)
            file_fields (str): Comma-separated list of file fields that should be returned in the metadata
                results (ref: https://developers.google.com/drive/api/v3/reference/files#resource)

        Returns:
            list of dict: A dict of metadata for each file that matched the given query
        """
        extra_list_params = {}
        if self.supports_team_drives:
            extra_list_params.update(
                dict(
                    corpora="teamDrive",
                    teamDriveId=settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID,
                    supportsTeamDrives=True,
                    includeTeamDriveItems=True,
                )
            )
        return self.pygsheets_client.drive.list(
            **extra_list_params, fields="files({})".format(file_fields), q=query
        )

    def update_spreadsheet_properties(self, file_id, property_dict):
        """
        Sets metadata properties on the spreadsheet, which can then be
        included in queries.

        Args:
            file_id (str): The spreadsheet ID
            property_dict (dict): Dict of properties to set

        Returns:
            dict: Google Drive API response to the files.update request
        """
        return (
            self.pygsheets_client.drive.service.files()
            .update(
                fileId=file_id,
                body={"appProperties": property_dict},
                supportsTeamDrives=self.supports_team_drives,
            )
            .execute()
        )

    def get_drive_file_metadata(self, file_id, fields="id, name, modifiedTime"):
        """
        Helper method to fetch metadata for some Drive file.

        Args:
           file_id (str): The file ID
           fields (str): Comma-separated list of file fields that should be returned in the metadata
                results (ref: https://developers.google.com/drive/api/v3/reference/files#resource)

        Returns:
           dict: The file metadata, which includes the specified fields.
        """
        return (
            self.pygsheets_client.drive.service.files()
            .get(
                fileId=file_id,
                fields=fields,
                supportsTeamDrives=self.supports_team_drives,
            )
            .execute()
        )

    def get_sheet_properties(self, file_id):
        """
        Helper method to fetch the dictionary of appProperties for the given spreadsheet by its
        file ID. The Google Sheets API doesn't know about this data. Only the Drive API can access
        it, hence this helper method.

        Args:
            file_id (str): The spreadsheet ID

        Returns:
            dict: appProperties (if any) for the given sheet according to Drive
        """
        result = self.get_drive_file_metadata(file_id=file_id, fields="appProperties")
        if result and "appProperties" in result:
            return result["appProperties"]
        return {}

    def batch_update_sheet_cells(self, sheet_id, request_objects):
        """
        Performs a batch update of targeted cells in a spreadsheet.

        Args:
            sheet_id (str): The spreadsheet id
            request_objects (list of dict): Update request objects
                (docs: https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/request#Request)

        Returns:
            dict: Google API response to the spreadsheets.values.batchUpdate request
        """
        return (
            self.pygsheets_client.sheet.service.spreadsheets()
            .batchUpdate(spreadsheetId=sheet_id, body={"requests": request_objects})
            .execute()
        )


def build_drive_service(credentials=None):
    """
    Builds the Google API client Drive service for API functionality that cannot be implemented correctly
    with pygsheets.

    Args:
        credentials (google.oauth2.credentials.Credentials or None): Credentials to be used by the
            Google Drive client

    Returns:
        googleapiclient.discovery.Resource: The Drive API service. The methods available on this resource are
            defined dynamically (ref: http://googleapis.github.io/google-api-python-client/docs/dyn/drive_v3.html)
    """
    credentials = credentials or get_credentials()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def request_file_watch(
    file_id, channel_id, handler_url, expiration=None, credentials=None
):
    """
    Sends a request to the Google API to watch for changes in a given file. If successful, this
    app will receive requests from Google when changes are made to the file.
    Ref: https://developers.google.com/drive/api/v3/reference/files/watch
    Args:
        file_id (str): The id of the file in Google Drive (can be determined from the URL)
        channel_id (str): Arbitrary string to identify the file watch being set up. This will
            be included in the header of every request Google sends to the app.
        handler_url (str): The URL stub for the xpro endpoint that should be called from Google's end when the file
            changes.
        expiration (datetime.datetime or None): The datetime that this file watch should expire.
            Defaults to 1 hour, and cannot exceed 24 hours.
        credentials (google.oauth2.credentials.Credentials or None): Credentials to be used by the
            Google Drive client
    Returns:
        dict: The Google file watch API response
    """
    drive_service = build_drive_service(credentials=credentials)
    extra_body_params = {}
    if expiration:
        extra_body_params["expiration"] = format_datetime_for_google_timestamp(
            expiration
        )
    return (
        drive_service.files()
        .watch(
            fileId=file_id,
            supportsTeamDrives=True,
            body={
                "id": channel_id,
                "resourceId": file_id,
                "address": urljoin(settings.SITE_BASE_URL, handler_url),
                "payload": True,
                "kind": GOOGLE_API_FILE_WATCH_KIND,
                "type": GOOGLE_API_NOTIFICATION_TYPE,
                **extra_body_params,
            },
        )
        .execute()
    )
