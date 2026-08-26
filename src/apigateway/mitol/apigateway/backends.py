"""Authentication backends for the API Gateway."""

import logging

from asgiref.sync import sync_to_async
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Q
from mitol.apigateway.api import decode_x_header
from mitol.apigateway.hooks import run_user_sync_hooks

log = logging.getLogger(__name__)
User = get_user_model()


def _with_updated_on(instance, fields: list[str]) -> list[str]:
    """
    Append updated_on to the fields if the model has it.

    auto_now fields are only written when explicitly included in update_fields.
    """
    try:
        instance._meta.get_field("updated_on")  # noqa: SLF001
    except FieldDoesNotExist:
        return list(fields)
    return [*fields, "updated_on"]


class RemoteUserCustomFieldBackend(RemoteUserBackend):
    """
    RemoteUserBackend variant that allows the field for the lookup to be configured
    """

    lookup_field: str

    def resolve_user(self, request, username):
        """
        Resolve the user for the cleaned username.

        Returns:
            tuple[User | None, bool]: the user (or None) and whether it was created
        """
        # if the current user and the user from the backend match, use it
        # directly - no lookup queries needed. (request may also be a channels
        # scope dict, which has no user attribute.)
        request_user = getattr(request, "user", None)
        if (
            request_user is not None
            and getattr(request_user, self.lookup_field, None) == username
        ):
            return request_user, False

        if self.create_unknown_user:
            return User.objects.get_or_create(**{self.lookup_field: username})

        try:
            return User.objects.get_by_natural_key(username), False
        except User.DoesNotExist:
            return None, False

    def authenticate(self, request, remote_user):
        """
        Authenticate the user
        """
        if not remote_user:
            return None

        username = self.clean_username(remote_user)
        user, created = self.resolve_user(request, username)

        if user is None:
            return None

        user = self.configure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None

    async def aauthenticate(self, request, remote_user):
        """See authenticate().

        Delegates to the sync ``authenticate()`` (via ``sync_to_async``): the
        sync path may wrap ORM calls in a plain ``transaction.atomic()`` block,
        which can't run from an async context (Django raises
        ``SynchronousOnlyOperation``).
        """
        if not remote_user:
            return None
        return await sync_to_async(self.authenticate, thread_sensitive=True)(
            request, remote_user
        )


class ApisixRemoteUserBackend(RemoteUserCustomFieldBackend):
    """
    Custom RemoteUserBackend that updates users using the APISIX headers.

    RemoteUserBackend already has some support for creating an unknown user, but
    it won't fill out all the data we'll generally want to capture. Additionally,
    we'll want to toggle the user creation code with a setting.
    """

    # these are properties (not class attributes) so the settings are read at
    # call time - overrides and test fixtures work as expected

    @property
    def lookup_field(self) -> str:
        """The user model field used to look up the user"""
        return settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD

    @property
    def create_unknown_user(self) -> bool:
        """Whether to create users we haven't seen before"""
        return settings.MITOL_APIGATEWAY_USERINFO_CREATE

    @property
    def update_known_user(self) -> bool:
        """Whether to update users we have seen before"""
        return settings.MITOL_APIGATEWAY_USERINFO_UPDATE

    def _mapped_user_defaults(self, decoded_headers: dict) -> dict:
        """Map header values to user model fields, for initial creation."""
        defaults = {}

        for header_field, model_field in settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP[
            "user_fields"
        ].items():
            field_name = (
                model_field[0] if isinstance(model_field, tuple) else model_field
            )

            if header_field not in decoded_headers:
                continue

            if field_name == self.lookup_field:
                # already supplied by the get_or_create kwargs
                continue

            try:
                User._meta.get_field(field_name)  # noqa: SLF001
            except FieldDoesNotExist:
                continue

            defaults[field_name] = decoded_headers[header_field]

        return defaults

    def resolve_user(self, request, username):
        """
        Resolve the user, optionally falling back to an email match.

        With MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK enabled, a user whose
        lookup field is unset (NULL or "") can be matched by email; the lookup
        field is backfilled immediately (identity linking is deliberately not
        gated by MITOL_APIGATEWAY_USERINFO_UPDATE). An ambiguous match fails
        closed and resolves to no user.
        """
        request_user = getattr(request, "user", None)
        if (
            request_user is not None
            and getattr(request_user, self.lookup_field, None) == username
        ):
            return request_user, False

        decoded_headers = decode_x_header(request) or {}
        query = Q(**{self.lookup_field: username})

        if settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK:
            email = decoded_headers.get(settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FIELD)
            if email:
                lookup_unset = Q(**{f"{self.lookup_field}__isnull": True}) | Q(
                    **{self.lookup_field: ""}
                )
                query |= lookup_unset & Q(email=email)

        try:
            user = User.objects.get(query)
        except User.MultipleObjectsReturned:
            log.exception(
                "Ambiguous gateway identity for %s=%s",
                self.lookup_field,
                username,
            )
            return None, False
        except User.DoesNotExist:
            if not self.create_unknown_user:
                log.debug(
                    "resolve_user: user %s not found and user creation is disabled",
                    username,
                )
                return None, False
            return User.objects.get_or_create(
                **{self.lookup_field: username},
                defaults=self._mapped_user_defaults(decoded_headers),
            )

        if getattr(user, self.lookup_field, None) != username:
            # matched by email - backfill the identity link
            setattr(user, self.lookup_field, username)
            user.save(update_fields=_with_updated_on(user, [self.lookup_field]))

        return user, False

    def authenticate(self, request, remote_user):
        """
        Authenticate the user
        """
        try:
            with transaction.atomic():
                return super().authenticate(request, remote_user)
        except Exception:
            log.exception("Unable to authenticate api gateway user")
            return None

    def _apply_user_fields(self, user, decoded_headers) -> list[str]:
        """Apply mapped header values to the user, returning the dirty fields."""
        infomap = settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP
        dirty_fields = []

        for header_field, model_field in infomap["user_fields"].items():
            if header_field not in decoded_headers:
                # don't overwrite fields the gateway didn't send
                continue
            value = decoded_headers[header_field]

            if isinstance(model_field, tuple):
                # If the model_field is a tuple, it means we have a flag for not
                # updating the value.
                field_name, override = model_field
                default_value = User._meta.get_field(field_name).get_default()  # noqa: SLF001
                field_not_set = getattr(user, field_name) == default_value
                if not override and not field_not_set:
                    continue
            else:
                field_name = model_field

            if getattr(user, field_name, None) == value:
                continue

            setattr(user, field_name, value)

            try:
                User._meta.get_field(field_name)  # noqa: SLF001
            except FieldDoesNotExist:
                # transient attribute, not a stored field
                continue

            dirty_fields.append(field_name)

        return dirty_fields

    def _sync_additional_models(self, user, decoded_headers):
        """Create or dirty-update the additional_models rows for the user."""
        infomap = settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP

        for model_name, field_map in infomap["additional_models"].items():
            AdditionalModel = apps.get_model(model_name)

            model_fields = {
                model_field: decoded_headers.get(header_field, default_value)
                for header_field, model_field, default_value in field_map
            }

            addl_model, addl_created = AdditionalModel.objects.get_or_create(
                user=user,
                defaults=model_fields,
            )

            if not addl_created:
                addl_dirty = [
                    field
                    for field, value in model_fields.items()
                    if getattr(addl_model, field, None) != value
                ]
                if addl_dirty:
                    for field in addl_dirty:
                        setattr(addl_model, field, model_fields[field])
                    addl_model.save(
                        update_fields=_with_updated_on(addl_model, addl_dirty)
                    )

            log.debug("configure_user: Updated model %s: %s", model_name, addl_model)

    def configure_user(self, request, user, *, created=True):
        """
        Configure the user - use the mapping to fill out the object(s).

        See MITOL_APIGATEWAY_USERINFO_MODEL_MAP in settings.py for the mapping.
        See also the flags above to configure when this updates the user object.

        Updates are dirty-checked: nothing is saved unless a mapped value
        actually changed, and saves are limited to the changed fields.
        """

        if not created and not self.update_known_user:
            log.debug("configure_user: Not updating known user %s", user)
            return user

        if created and not self.create_unknown_user:
            log.debug("configure_user: Not updating created user %s", user)
            return user

        decoded_headers = decode_x_header(request) or {}

        dirty_fields = self._apply_user_fields(user, decoded_headers)

        if created:
            user.set_unusable_password()
            user.is_active = True
            user.save()
            log.debug("configure_user: Created user %s", user)
        elif dirty_fields:
            user.save(update_fields=_with_updated_on(user, dirty_fields))
            log.debug("configure_user: Updated user %s fields %s", user, dirty_fields)

        self._sync_additional_models(user, decoded_headers)

        run_user_sync_hooks(request, user, decoded_headers, created=created)

        return user
