"""Oauth toolkit and extensions factories"""
from factory import Faker, SelfAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
)

from mitol.oauth_toolkit_extensions.models import ApplicationAccess

DEFAULT_SCOPE = "custom_scope_1 custom_scope_2"

Grant = get_grant_model()


class GrantFactory(DjangoModelFactory):
    """Factory for Grant"""

    user = SubFactory("mitol.common.factories.UserFactory")
    code = Sequence(lambda i: f"code_{i}")  # pragma: no cover
    application = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.ApplicationFactory"
    )
    expires = Faker("future_datetime")
    redirect_uri = "http://localhost:9999/redirect_complete"
    scope = DEFAULT_SCOPE

    class Meta:
        model = Grant


AccessToken = get_access_token_model()


class AccessTokenFactory(DjangoModelFactory):
    """Factory for AccessToken"""

    user = SubFactory("mitol.common.factories.UserFactory")
    source_refresh_token = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.RefreshTokenFactory"
    )
    token = Sequence(lambda i: f"token_{i}")  # pragma: no cover
    application = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.ApplicationFactory"
    )
    expires = Faker("future_datetime")
    scope = SelfAttribute("source_refresh_token.scope")

    class Meta:
        model = get_access_token_model()


RefreshToken = get_refresh_token_model()


class RefreshTokenFactory(DjangoModelFactory):
    """Factory for RefreshToken"""

    user = SubFactory("mitol.common.factories.UserFactory")
    token = Sequence(lambda i: f"token_{i}")  # pragma: no cover
    application = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.ApplicationFactory"
    )
    access_token = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.AccessTokenFactory"
    )

    scope = DEFAULT_SCOPE
    expires = Faker("future_datetime")

    class Meta:
        model = RefreshToken


Application = get_application_model()


class ApplicationFactory(DjangoModelFactory):
    """Factory for Application"""

    user = SubFactory("mitol.common.factories.UserFactory")
    redirect_uris = "http://localhost:9999/redirect_complete"
    client_type = FuzzyChoice(
        (client_type for client_type, _ in Application.CLIENT_TYPES)
    )
    authorization_grant_type = FuzzyChoice(
        (grant_type for grant_type, _ in Application.GRANT_TYPES)
    )

    name = Sequence(lambda i: f"application_{i}")

    class Meta:
        model = Application


class ApplicationAccessFactory(DjangoModelFactory):
    """Factory for ApplicationAccess"""

    application = SubFactory(
        "mitol.oauth_toolkit_extensions.factories.ApplicationFactory"
    )

    scopes = ["custom_scope_1", "custom_scope_2"]

    class Meta:
        model = ApplicationAccess
