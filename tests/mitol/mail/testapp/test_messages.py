"""Messages tests"""

from testapp.messages import SampleMessage


def test_create_message_subclass(mocker):
    """Test that SampleMessage renders correctly"""
    user = mocker.Mock(first_name="Sally")
    message = SampleMessage.create(
        to=["user@localhost"], template_context={"user": user}
    )

    assert message.subject == "Welcome Sally"
    # from this app's templates
    assert "Test Logo" in message.alternatives[0][0]
    assert "Test Content" in message.alternatives[0][0]
    # from the base template
    assert (
        "MIT, 77 Massachusetts Avenue, Cambridge, MA 02139"
        in message.alternatives[0][0]
    )


def test_debug_message_subclass():
    """Test that SampleMessage debug renders correctly"""
    message = SampleMessage.debug()

    assert message.subject == "Welcome Sally"
    # from this app's templates
    assert "Test Logo" in message.alternatives[0][0]
    assert "Test Content" in message.alternatives[0][0]
    # from the base template
    assert (
        "MIT, 77 Massachusetts Avenue, Cambridge, MA 02139"
        in message.alternatives[0][0]
    )
