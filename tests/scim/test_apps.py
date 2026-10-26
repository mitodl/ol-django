"""Tests for the SCIM app config"""

import pytest
from django.core.exceptions import ImproperlyConfigured
from mitol.scim.apps import validate_username_filter_fields


def test_username_filter_fields_accepts_columns(settings):
    """Configured user columns pass validation"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["scim_username", "email", ""]

    validate_username_filter_fields()


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("emial", "has no field 'emial'"),
        ("groups", "'groups' must be a column"),
    ],
)
def test_username_filter_fields_rejects_non_columns(settings, field_name, message):
    """A typo or a relation fails at startup instead of on the first lookup"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email", field_name]

    with pytest.raises(ImproperlyConfigured, match=message):
        validate_username_filter_fields()
