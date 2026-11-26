"""Hubspot admin tests"""

from http import HTTPStatus

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from mitol.common.factories import UserFactory
from mitol.hubspot_api.factories import GroupFactory
from mitol.hubspot_api.models import HubspotObject

pytestmark = pytest.mark.django_db


def _create_hubspot_objects(count):
    """Create HubspotObjects pointing at a mix of users and groups"""
    for idx in range(count):
        content_object = (UserFactory if idx % 2 else GroupFactory).create()
        HubspotObject.objects.create(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.id,
            hubspot_id=str(content_object.id),
        )


def _changelist_query_count(client):
    """Load the changelist and return the number of queries it ran"""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("admin:hubspot_api_hubspotobject_changelist"))
    assert response.status_code == HTTPStatus.OK
    return len(queries)


def test_changelist_query_count_is_constant(admin_client):
    """The changelist query count should not grow with the number of rows"""
    _create_hubspot_objects(2)
    small = _changelist_query_count(admin_client)
    _create_hubspot_objects(10)
    assert _changelist_query_count(admin_client) == small


def test_stale_content_type_pages_load(admin_client):
    """Rows whose model no longer exists should not break the admin"""
    stale_type = ContentType.objects.create(app_label="gone_app", model="gonemodel")
    obj = HubspotObject.objects.create(
        content_type=stale_type, object_id=1, hubspot_id="stale"
    )
    for name, args in [
        ("changelist", []),
        ("change", [obj.id]),
        ("delete", [obj.id]),
    ]:
        url = reverse(f"admin:hubspot_api_hubspotobject_{name}", args=args)
        assert admin_client.get(url).status_code == HTTPStatus.OK, name
    response = admin_client.post(
        reverse("admin:hubspot_api_hubspotobject_changelist"),
        {"action": "delete_selected", "_selected_action": [obj.id], "post": "yes"},
    )
    assert response.status_code == HTTPStatus.FOUND
    assert not HubspotObject.objects.filter(id=obj.id).exists()
