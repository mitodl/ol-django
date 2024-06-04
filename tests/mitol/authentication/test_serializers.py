import pytest
from mitol.authentication.serializers.djoser_serializers import (
    CustomSendEmailResetSerializer,
)
from mitol.common.factories import UserFactory

pytestmark = pytest.mark.django_db
EMAIL = "email@example.com"


@pytest.mark.parametrize(
    "email,exists",
    (
        ("email@example.com", True),
        ("EmaIl@example.com", True),
        ("falseemail@example.com", False),
    ),
)
def test_forgot_password_case_insensitive(email, exists):
    """Test that CustomEmailResetSerializer is case insensitive"""

    user = UserFactory.create(email=EMAIL) if exists else None
    serializer = CustomSendEmailResetSerializer(data={"email": email})
    assert serializer.is_valid() is True
    assert serializer.get_user() == user
