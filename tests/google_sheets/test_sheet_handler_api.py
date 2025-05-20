import pytest
from mitol.google_sheets.sheet_handler_api import SheetHandler
from pytest_lazy_fixtures import lf as lazy_fixture


@pytest.mark.usefixtures("google_sheets_base_settings")
@pytest.mark.parametrize(
    "_creds",
    [
        lazy_fixture("google_sheets_service_creds_settings"),
        lazy_fixture("google_sheets_client_creds_settings"),
    ],
)
def test_is_configured_missing(_creds):
    """Test that is_configured returns correctly"""
    handler = SheetHandler()
    assert handler.is_configured() is True
