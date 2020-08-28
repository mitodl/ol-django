"""Message tests"""
import pytest

from mitol.mail.messages import TemplatedMessage


class NoNameMessage(TemplatedMessage):
    template_name = "testtemplatename"


class NoTemplateNameMessage(TemplatedMessage):
    name = "testname"


@pytest.fixture(autouse=True)
def default_settings(settings):
    """Default settings for tests"""
    settings.SITE_BASE_URL = "http://mit.edu/"
    settings.SITE_NAME = "MIT"
    settings.MITOL_MAIL_REPLY_TO_ADDRESS = "user@localhost"


def test_static_methods(settings):
    """Test TemplatedMessage's static methods"""
    assert TemplatedMessage.get_base_template_context() == {
        "base_url": settings.SITE_BASE_URL,
        "site_name": settings.SITE_NAME,
    }
    assert TemplatedMessage.get_debug_template_context() == {}
    assert TemplatedMessage.get_default_headers() == {
        "Reply-To": settings.MITOL_MAIL_REPLY_TO_ADDRESS
    }


def test_create_validations():
    """Verify the create() function validates the subclass setup"""
    with pytest.raises(ValueError) as exc_info:
        NoNameMessage.create()

    assert exc_info.value.args[0] == "NoNameMessage.name not defined"

    with pytest.raises(ValueError) as exc_info:
        NoTemplateNameMessage.create()

    assert exc_info.value.args[0] == "NoTemplateNameMessage.template_name not defined"
