"""Authentication backends for the API Gateway."""

import contextlib
import logging

from asgiref.sync import sync_to_async
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models.functions import Lower
from mitol.apigateway.api import decode_x_header
from mitol.common.utils.config import SettingsRef

log = logging.getLogger(__name__)
User = get_user_model()


def _concrete_field_names(model) -> set[str]:
    """Return the names and attnames (e.g. ``org_id``) of the concrete fields."""
    fields = model._meta.concrete_fields  # noqa: SLF001
    return {field.name for field in fields} | {field.attname for field in fields}


def _save_changed(instance, changed: list[str]):
    """
    Save only the changed fields, plus any auto_now timestamp.

    update_fields skips an auto_now field's pre_save unless it is listed, so
    a timestamp like updated_on would otherwise go stale.
    """
    auto_now = [
        field.attname
        for field in instance._meta.concrete_fields  # noqa: SLF001
        if getattr(field, "auto_now", False) and field.attname not in changed
    ]
    instance.save(update_fields=[*changed, *auto_now])


class RemoteUserCustomFieldBackend(RemoteUserBackend):
    """
    RemoteUserBackend variant that allows the field for the lookup to be configured
    """

    lookup_field: str

    def authenticate(self, request, remote_user):
        """
        Authenticate the user.

        If the request's current user already matches ``remote_user`` on the
        lookup field, that user is reused rather than looked up again, but it
        still goes through ``configure_user`` so updates can be applied.

        :param request: the HTTP request, or a Channels scope dict
        :param remote_user: the lookup field value from the gateway
        :returns: the authenticated user, or None
        """
        if not remote_user:
            return None
        created = False
        user = None
        username = self.clean_username(remote_user)

        # A Channels scope is a dict, so it has no user attribute.
        request_user = getattr(request, "user", None)
        if getattr(request_user, self.lookup_field, None) == username:
            user = request_user
        elif self.create_unknown_user:
            user, created = self.get_or_create_user(request, username)
        else:
            with contextlib.suppress(User.DoesNotExist):
                user = User.objects.get(**{self.lookup_field: username})

        if user is None:
            return None

        user = self.configure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None

    def get_or_create_user(self, request, username):
        """
        Find the user whose lookup field is ``username``, creating it if absent.

        The row is inserted with ``new_user_defaults()`` already applied. Left
        to ``configure_user`` to fill in afterward, it would be inserted with
        empty values, and two concurrent first logins would collide on any
        unique column holding the same empty value (e.g. ``username=""``).

        :param request: the HTTP request, or a Channels scope dict
        :param username: the cleaned lookup field value
        :returns: a ``(user, created)`` pair; ``user`` is None if creation was
            refused
        """
        return User.objects.get_or_create(
            **{self.lookup_field: username},
            defaults=self.new_user_defaults(request),
        )

    def new_user_defaults(self, request):  # noqa: ARG002
        """
        Return the field values a user created from the gateway starts with.

        The identity provider holds the credentials, so the user gets an
        unusable password: an empty one counts as usable to Django, so password
        reset would offer to set one.

        :param request: the HTTP request, or a Channels scope dict
        :returns: a dict of model field values
        """
        defaults = {"password": make_password(None)}
        if "is_active" in _concrete_field_names(User):
            defaults["is_active"] = True
        return defaults

    async def aauthenticate(self, request, remote_user):
        """
        See authenticate().

        Delegates to the sync ``authenticate()`` via ``sync_to_async``. A
        subclass may wrap ``authenticate()`` in ``transaction.atomic()``,
        which raises ``SynchronousOnlyOperation`` from an async context.
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

    lookup_field = SettingsRef("MITOL_APIGATEWAY_USER_LOOKUP_FIELD")
    create_unknown_user = SettingsRef("MITOL_APIGATEWAY_USERINFO_CREATE")
    update_known_user = SettingsRef("MITOL_APIGATEWAY_USERINFO_UPDATE")

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

    def get_or_create_user(self, request, username):
        """
        See RemoteUserCustomFieldBackend.get_or_create_user().

        An unknown identity whose email belongs only to inactive accounts is
        refused rather than given a new, active account. The inactive account
        was deactivated deliberately (retired, merged, banned), and a second
        account with the same email would undo that and split the person's
        data. Reactivating or relinking the old account is an administrator's
        call. An email that an active account also holds is not refused here;
        matching an existing account by email is a separate adoption policy.
        """
        with contextlib.suppress(User.DoesNotExist):
            return User.objects.get(**{self.lookup_field: username}), False

        inactive_user_id = self.inactive_user_with_email(request)
        if inactive_user_id is not None:
            log.warning(
                "get_or_create_user: refused_inactive_email_match %s=%s "
                "inactive_user_id=%s",
                self.lookup_field,
                username,
                inactive_user_id,
            )
            return None, False

        return super().get_or_create_user(request, username)

    def inactive_user_with_email(self, request):
        """
        Return the pk of an inactive user with the header's email.

        Emails compare case-insensitively through Lower(), which an index on
        LOWER(email) can serve; __iexact compiles to UPPER() on Postgres.

        :param request: the HTTP request, or a Channels scope dict
        :returns: an inactive user's pk, or None if there is none or an active
            user also holds the email
        """
        if "is_active" not in _concrete_field_names(User):
            return None
        email_field = User.get_email_field_name()
        email = self.mapped_user_defaults(request).get(email_field)
        if not email:
            return None
        matches = list(
            User.objects.alias(_email_lower=Lower(email_field))
            .filter(_email_lower=email.lower())
            .order_by("pk")
            .values_list("pk", "is_active")
        )
        if any(is_active for _, is_active in matches):
            return None
        return next((pk for pk, _ in matches), None)

    def new_user_defaults(self, request):
        """Add the mapped header values to the base defaults."""
        return {
            **super().new_user_defaults(request),
            **self.mapped_user_defaults(request),
        }

    def mapped_user_defaults(self, request):
        """
        Map the header values present in the request onto user model columns.

        Only concrete columns are returned: these feed get_or_create(), which
        can't take an arbitrary attribute. configure_user() applies the rest.

        :param request: the HTTP request, or a Channels scope dict
        :returns: a dict of model field values
        """
        decoded_headers = decode_x_header(request) or {}
        concrete_fields = _concrete_field_names(User)
        defaults = {}
        for header_field, model_field in settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP[
            "user_fields"
        ].items():
            field_name = (
                model_field[0] if isinstance(model_field, tuple) else model_field
            )
            if (
                header_field in decoded_headers
                and field_name in concrete_fields
                and field_name != self.lookup_field
            ):
                defaults[field_name] = decoded_headers[header_field]
        return defaults

    def configure_user(self, request, user, *, created=True):
        """
        Configure the user - use the mapping to fill out the object(s).

        See MITOL_APIGATEWAY_USERINFO_MODEL_MAP in settings.py for the mapping.
        See also the flags above to configure when this updates the user object.

        A field whose header key is absent from the userinfo is left as it is,
        and a model is only written when a mapped value differs from what it
        holds. With MITOL_APIGATEWAY_USERINFO_UPDATE on this runs on every
        request, so an unconditional save would put the app's whole request
        volume onto the users table, and a full-row save would overwrite
        concurrent writes to columns the map doesn't cover.
        """

        if not created and not self.update_known_user:
            log.debug("configure_user: Not updating known user %s", user)
            return user

        if created and not self.create_unknown_user:
            log.debug("configure_user: Not updating created user %s", user)
            return user

        infomap = settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP
        decoded_headers = decode_x_header(request) or {}

        self._sync_user_fields(user, infomap["user_fields"], decoded_headers)
        self._sync_additional_models(
            user, infomap["additional_models"], decoded_headers
        )

        return user

    def _sync_user_fields(self, user, user_fields, decoded_headers):
        """
        Copy the mapped header values onto the user, saving only changed columns.

        Columns are compared before and after, rather than per mapped name, so
        a mapped settable property (e.g. a name split into first and last)
        saves the columns it changed, and one whose getter normalizes the value
        it was given doesn't write on every request.
        """
        columns = [field.attname for field in User._meta.concrete_fields]  # noqa: SLF001
        before = {column: getattr(user, column) for column in columns}

        for header_field, model_field in user_fields.items():
            if header_field not in decoded_headers:
                continue
            value = decoded_headers[header_field]
            if isinstance(model_field, tuple):
                # A tuple carries a flag: when False, only fill in an unset value.
                field_name, override = model_field
                default_value = User._meta.get_field(field_name).get_default()  # noqa: SLF001
                if not override and getattr(user, field_name) != default_value:
                    continue
            else:
                field_name = model_field

            setattr(user, field_name, value)

        changed = [
            column for column in columns if getattr(user, column) != before[column]
        ]
        if changed:
            _save_changed(user, changed)
            log.debug("configure_user: Updated user %s fields %s", user, changed)

    def _sync_additional_models(self, user, additional_models, decoded_headers):
        """
        Update the mapped related models, saving only those that changed.

        A field's default applies only when the related row is created. On an
        existing row a header key absent from the userinfo leaves the field as
        it is.
        """
        for model_name, field_specs in additional_models.items():
            AdditionalModel = apps.get_model(model_name)
            addl_model, created = AdditionalModel.objects.get_or_create(
                user=user,
                defaults={
                    model_field: decoded_headers.get(header_field, default_value)
                    for header_field, model_field, default_value in field_specs
                },
            )
            if created:
                log.debug(
                    "configure_user: Created model %s: %s", model_name, addl_model
                )
                continue

            changed = []
            for header_field, model_field, _ in field_specs:
                if header_field not in decoded_headers:
                    continue
                value = decoded_headers[header_field]
                if getattr(addl_model, model_field) != value:
                    setattr(addl_model, model_field, value)
                    changed.append(model_field)
            if changed:
                _save_changed(addl_model, changed)
                log.debug(
                    "configure_user: Updated model %s: %s fields %s",
                    model_name,
                    addl_model,
                    changed,
                )
