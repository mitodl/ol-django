"""Create or refresh the bearer token a SCIM client authenticates with"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from mitol.scim.constants import SERVICE_ACCOUNT_EMAIL_DOMAIN, is_service_account_email
from oauth2_provider.models import get_access_token_model
from oauthlib.common import generate_token

DEFAULT_SCOPE = "scim"
DEFAULT_EXPIRES_DAYS = 365


def _service_account_problem(user) -> str | None:
    """Say why an existing user is not a SCIM service account, or None if it is.

    The account this command creates has a service-account email, has never
    logged in, has no usable password and no SSO identity, so an existing row
    with any of those is a person, and turning it into a staff token owner
    would escalate them.
    """
    if not is_service_account_email(user.email):
        return f"has an email outside @{SERVICE_ACCOUNT_EMAIL_DOMAIN}"
    if not user.is_active:
        return "is inactive"
    if user.has_usable_password():
        return "has a usable password"
    if user.last_login is not None:
        return "has logged in"
    if getattr(user, "global_id", None):
        return "has an SSO global_id"
    return None


def _service_account(username: str):
    """Get or create the service account, refusing anyone who is not one.

    :param username: Username of the service account.
    :returns: The user and whether it was created.
    :rtype: tuple
    """
    User = get_user_model()
    email = f"{username.partition('@')[0]}@{SERVICE_ACCOUNT_EMAIL_DOMAIN}"
    if User.objects.filter(email__iexact=email).exclude(username=username).exists():
        msg = (
            f"Another user already has the email {email}; choose a --username "
            "with a different local part"
        )
        raise CommandError(msg)
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_active": True},
    )
    if created:
        user.set_unusable_password()
        user.save()
        return user, created
    problem = _service_account_problem(user)
    if problem:
        msg = (
            f"User {username!r} {problem}, so it is not a SCIM service account; "
            "choose another --username"
        )
        raise CommandError(msg)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    return user, created


def _write_token(user, token_value: str, scope: str, expires) -> bool:
    """Create the token for ``user``, or refresh it if ``user`` already owns it.

    :returns: Whether the token row was created.
    :rtype: bool
    """
    # Lock the row before checking who owns it, so two concurrent runs cannot
    # both pass the check and the second overwrite the first.
    token, created = (
        get_access_token_model()
        .objects.select_for_update()
        .get_or_create(
            token=token_value,
            defaults={"user": user, "scope": scope, "expires": expires},
        )
    )
    if created:
        return created
    if token.user_id != user.pk or token.application_id is not None:
        msg = (
            "That token value already belongs to another user or OAuth "
            "application; choose a different value"
        )
        raise CommandError(msg)
    token.scope = scope
    token.expires = expires
    token.save(update_fields=["scope", "expires"])
    return created


class Command(BaseCommand):
    """Create or refresh the bearer token a SCIM client authenticates with.

    The SCIM views accept a django-oauth-toolkit access token whose user passes
    mitol.scim.utils.is_authenticated_predicate (active and staff). This creates
    that user as a staff service account with no usable password and an email
    under the reserved SERVICE_ACCOUNT_EMAIL_DOMAIN, which marks it as one: the
    client sync skips it and the command only ever reuses such an account.

    Running it again with the same token value refreshes that token's scope and
    expiry instead of adding a row. Running it without a token value adds
    another token and leaves the earlier ones valid until they expire.
    """

    help = "Create or refresh the bearer token a SCIM client authenticates with"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Username of the service account that owns the token. Its email "
            f"is <local part of the username>@{SERVICE_ACCOUNT_EMAIL_DOMAIN}.",
        )
        parser.add_argument(
            "--token",
            help="Token value to write. A random one is generated and printed "
            "when omitted.",
        )
        parser.add_argument(
            "--scope",
            default=DEFAULT_SCOPE,
            help=f"Space-separated OAuth2 scopes (default: {DEFAULT_SCOPE})",
        )
        parser.add_argument(
            "--expires-days",
            type=int,
            default=DEFAULT_EXPIRES_DAYS,
            help=f"Days until the token expires (default: {DEFAULT_EXPIRES_DAYS})",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Create or refresh the token"""
        username = options["username"]
        token_value = options["token"]
        if token_value == "":
            msg = "The token value must not be empty"
            raise CommandError(msg)
        if options["expires_days"] <= 0:
            msg = "--expires-days must be positive"
            raise CommandError(msg)
        if DEFAULT_SCOPE not in options["scope"].split():
            self.stderr.write(
                f"Warning: scope {options['scope']!r} lacks {DEFAULT_SCOPE!r}; "
                "apps that check the scope will reject this token"
            )
        generated = token_value is None
        if generated:
            token_value = generate_token()

        expires = timezone.now() + timedelta(days=options["expires_days"])
        with transaction.atomic():
            user, user_created = _service_account(username)
            token_created = _write_token(user, token_value, options["scope"], expires)

        self.stdout.write(
            f"{'Created' if user_created else 'Reused'} service account "
            f"{user.username}; {'created' if token_created else 'refreshed'} "
            f"token with scope {options['scope']!r}"
        )
        if generated:
            self.stdout.write(token_value)
