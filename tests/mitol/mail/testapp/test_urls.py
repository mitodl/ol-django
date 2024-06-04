"""URLs tests"""

from django.urls import reverse


def test_included_urls(client):
    """Test that the debugger is included"""
    assert client.get(reverse("email-debugger")).status_code == 200
