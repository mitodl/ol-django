"""Create or refresh the bearer token a SCIM client authenticates with"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from oauth2_provider.models import get_access_token_model
from oauthlib.common import generate_token

DEFAULT_SCOPE = "scim"
DEFAULT_EXPIRES_DAYS = 365
# Reserved TLD (RFC 2606): the service account's email can never belong to a
# real person, so the client sync (scim_sync) can't match it to one in Keycloak.
SERVICE_EMAIL_DOMAIN = "scim.invalid"


def _service_account_problem(user) -> str | None:
    """Say why an existing user is not a SCIM service account, or None if it is.

    The account this command creates has never logged in, has no usable
    password and no SSO identity, so an existing row with any of those is a
    person, and turning it into a staff token owner would escalate them.
    """
    if not user.is_active:
        return "is inactive"
    if user.has_usable_password():
        return "has a usable password"
    if user.last_login is not None:
        return "has logged in"
    if getattr(user, "global_id", None):
        return "has an SSO global_id"
    return None


class Command(BaseCommand):
    """Create or refresh the bearer token a SCIM client authenticates with.

    The SCIM views accept a django-oauth-toolkit access token whose user passes
    mitol.scim.utils.is_authenticated_predicate (active and staff). This creates
    that user as a staff service account with no usable password and writes the
    token. Re-running with the same --token refreshes its scope and expiry
    instead of adding a row. Re-running without --token adds another token and
    leaves the earlier ones valid until they expire.
    """

    help = "Create or refresh the bearer token a SCIM client authenticates with"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Username of the service account that owns the token",
        )
        parser.add_argument(
            "--email",
            help="Email for the service account when it is created (defaults to "
            f"<local part of --username>@{SERVICE_EMAIL_DOMAIN})",
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
            msg = "--token must not be empty"
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

        User = get_user_model()
        AccessToken = get_access_token_model()
        email = (
            options["email"] or f"{username.partition('@')[0]}@{SERVICE_EMAIL_DOMAIN}"
        )

        with transaction.atomic():
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "is_staff": True, "is_active": True},
            )
            if user_created:
                user.set_unusable_password()
                user.save()
            else:
                problem = _service_account_problem(user)
                if problem:
                    msg = (
                        f"User {username!r} {problem}, so it is not a SCIM "
                        "service account; choose another --username"
                    )
                    raise CommandError(msg)
                if not user.is_staff:
                    user.is_staff = True
                    user.save(update_fields=["is_staff"])

            existing = AccessToken.objects.filter(token=token_value).first()
            if existing is not None and (
                existing.user_id != user.pk or existing.application_id is not None
            ):
                msg = (
                    "That --token already belongs to another user or OAuth "
                    "application; choose a different value"
                )
                raise CommandError(msg)

            _, token_created = AccessToken.objects.update_or_create(
                token=token_value,
                defaults={
                    "user": user,
                    "scope": options["scope"],
                    "expires": timezone.now() + timedelta(days=options["expires_days"]),
                },
            )

        self.stdout.write(
            f"{'Created' if user_created else 'Reused'} service account "
            f"{user.username}; {'created' if token_created else 'refreshed'} "
            f"token with scope {options['scope']!r}"
        )
        if generated:
            self.stdout.write(token_value)
