"""Authentication backends for the API Gateway."""

import logging

from asgiref.sync import sync_to_async
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend
from django.db import transaction
from django.db.models import Q
from mitol.apigateway.api import decode_x_header

log = logging.getLogger(__name__)
User = get_user_model()


class RemoteUserCustomFieldBackend(RemoteUserBackend):
    """
    RemoteUserBackend variant that allows the field for the lookup to be configured
    """

    lookup_field: str

    #: Field to match a pre-gateway account on when it has no lookup_field value
    #: yet, so it is adopted rather than duplicated. None disables adoption.
    adopt_unlinked_user_by: str | None = None

    def unlinked_user_filter(self, request) -> Q | None:
        """
        Build the filter matching a pre-gateway account for this request.

        Returns None when adoption is off, or when the request carries no value
        for the adoption field — matching every unlinked account on an empty
        value would hand the request an arbitrary stranger's account.
        """
        if not self.adopt_unlinked_user_by:
            return None

        infomap = settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP["user_fields"]
        header_field = next(
            (
                header
                for header, model_field in infomap.items()
                # A tuple value is (field_name, override_flag).
                if (model_field[0] if isinstance(model_field, tuple) else model_field)
                == self.adopt_unlinked_user_by
            ),
            None,
        )
        if header_field is None:
            log.error(
                "adopt_unlinked_user_by=%s is not in MITOL_APIGATEWAY_USERINFO_"
                "MODEL_MAP['user_fields']; adoption disabled",
                self.adopt_unlinked_user_by,
            )
            return None

        value = (decode_x_header(request) or {}).get(header_field)
        if not value:
            return None

        # A record that predates the gateway carries no lookup-field value, and
        # which empty it carries depends on the app's own column:
        # UserGlobalIdMixin declares blank=True default="", other apps declare
        # null=True. Both have to be matched separately - `__in=("", None)`
        # cannot do it, because SQL never matches NULL through IN and Django
        # drops the None from the list.
        unset = Q(**{self.lookup_field: ""}) | Q(
            **{f"{self.lookup_field}__isnull": True}
        )
        return unset & Q(**{self.adopt_unlinked_user_by: value})

    def resolve_user(self, request, username):
        """
        Find the user for this remote id, adopting or creating one if allowed.

        Returns an (user, created) pair. ``user`` is None when the identity is
        ambiguous, or unknown while create_unknown_user is off.
        """
        candidates = Q(**{self.lookup_field: username})
        unlinked = self.unlinked_user_filter(request)
        if unlinked is not None:
            candidates |= unlinked

        try:
            user = User.objects.get(candidates)
        except User.MultipleObjectsReturned:
            # Refuse rather than guess: picking one of several matches would
            # silently attach this login to the wrong account.
            log.exception(
                "Ambiguous remote identity: %s=%s matches more than one user",
                self.lookup_field,
                username,
            )
            return None, False
        except User.DoesNotExist:
            if not self.create_unknown_user:
                log.debug(
                    "resolve_user: no user for %s=%s and creation is disabled",
                    self.lookup_field,
                    username,
                )
                return None, False
            # get_or_create, not create: it re-runs the get inside a savepoint
            # and falls back to it on IntegrityError, so a concurrent request
            # that inserted this lookup value between our get and our insert
            # resolves to that row. A bare create would instead duplicate the
            # user where the column has no unique constraint, or raise where it
            # does - and an IntegrityError raised with no savepoint inside
            # authenticate()'s transaction.atomic() marks the whole transaction
            # for rollback.
            return User.objects.get_or_create(**{self.lookup_field: username})

        if getattr(user, self.lookup_field, None) != username:
            # Adopted a pre-gateway account: stamp it so the next request
            # matches on the lookup field directly.
            setattr(user, self.lookup_field, username)
            user.save(update_fields=[self.lookup_field])
            log.info(
                "resolve_user: adopted existing user %s by %s, set %s=%s",
                user.pk,
                self.adopt_unlinked_user_by,
                self.lookup_field,
                username,
            )

        return user, False

    def authenticate(self, request, remote_user):
        """
        Authenticate the user
        """
        if not remote_user:
            return None
        username = self.clean_username(remote_user)

        # if the current user and the user from the backend match
        # just return that user and do no further queries or configuration
        if getattr(request.user, self.lookup_field, None) == username:
            user = request.user
            return user if self.user_can_authenticate(user) else None

        user, created = self.resolve_user(request, username)
        if user is None:
            return None
        user = self.configure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None

    async def aauthenticate(self, request, remote_user):
        """See authenticate()."""
        if not remote_user:
            return None
        username = self.clean_username(remote_user)

        # if the current user and the user from the backend match
        # just return that user and do no further queries or configuration
        if getattr(request.user, self.lookup_field, None) == username:
            user = request.user
            return user if self.user_can_authenticate(user) else None

        user, created = await sync_to_async(self.resolve_user, thread_sensitive=True)(
            request, username
        )
        if user is None:
            return None
        user = await self.aconfigure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None


class ApisixRemoteUserBackend(RemoteUserCustomFieldBackend):
    """
    Custom RemoteUserBackend that updates users using the APISIX headers.

    RemoteUserBackend already has some support for creating an unknown user, but
    it won't fill out all the data we'll generally want to capture. Additionally,
    we'll want to toggle the user creation code with a setting.
    """

    lookup_field = settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD

    create_unknown_user = settings.MITOL_APIGATEWAY_USERINFO_CREATE
    update_known_user = settings.MITOL_APIGATEWAY_USERINFO_UPDATE
    adopt_unlinked_user_by = settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY

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

    async def aauthenticate(self, request, remote_user):
        """See authenticate().

        Delegates to the sync ``authenticate()`` (via ``sync_to_async``)
        rather than awaiting ``super().aauthenticate()`` directly: the
        latter's async ORM calls can't be wrapped in a plain
        ``transaction.atomic()`` block from an async context (Django raises
        ``SynchronousOnlyOperation``), and the sync path is the one covered
        by tests.
        """
        if not remote_user:
            return None
        return await sync_to_async(self.authenticate, thread_sensitive=True)(
            request, remote_user
        )

    def configure_user(self, request, user, *, created=True):
        """
        Configure the user - use the mapping to fill out the object(s).

        See MITOL_APIGATEWAY_USERINFO_MODEL_MAP in settings.py for the mapping.
        See also the flags above to configure when this updates the user object.
        """

        if not created and not self.update_known_user:
            log.debug("configure_user: Not updating known user %s", user)
            return user

        if created and not self.create_unknown_user:
            log.debug("configure_user: Not updating created user %s", user)
            return user

        infomap = settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP
        decoded_headers = decode_x_header(request)

        self._sync_user_fields(user, infomap["user_fields"], decoded_headers)
        self._sync_additional_models(
            user, infomap["additional_models"], decoded_headers
        )

        return user

    def _sync_user_fields(self, user, user_fields, decoded_headers):
        """Copy the mapped header values onto the user, saving only if changed."""
        # A mapped name need not be a concrete column - it can be a property
        # with a setter, which update_fields cannot express.
        concrete_fields = {f.name for f in User._meta.concrete_fields}  # noqa: SLF001
        changed = []
        changed_non_concrete = False

        for header_field, model_field in user_fields.items():
            value = decoded_headers.get(header_field, None)
            if isinstance(model_field, tuple):
                # If the model_field is a tuple, it means we have a flag for not
                # updating the value.
                model_field_name, override = model_field
                default_value = User._meta.get_field(model_field_name).get_default()  # noqa: SLF001
                field_not_set = getattr(user, model_field_name) == default_value
                if not override and not field_not_set:
                    continue
            else:
                model_field_name = model_field

            if getattr(user, model_field_name, None) == value:
                continue
            setattr(user, model_field_name, value)
            if model_field_name in concrete_fields:
                changed.append(model_field_name)
            else:
                changed_non_concrete = True

        # This runs on every authenticated request. Writing a row whose columns
        # already match the headers would put the whole request volume of the
        # app onto the users table for nothing.
        if changed_non_concrete:
            user.save()
            log.debug("configure_user: Updated user %s", user)
        elif changed:
            user.save(update_fields=changed)
            log.debug("configure_user: Updated user %s fields %s", user, changed)

    def _sync_additional_models(self, user, additional_models, decoded_headers):
        """Update the mapped related models, saving only those that changed."""
        for model_name, field_specs in additional_models.items():
            AdditionalModel = apps.get_model(model_name)
            model_fields = {
                model_field: decoded_headers.get(header_field, default_value)
                for header_field, model_field, default_value in field_specs
            }

            addl_model = AdditionalModel.objects.filter(user=user).first()
            if addl_model is not None and all(
                getattr(addl_model, field, None) == value
                for field, value in model_fields.items()
            ):
                continue

            addl_model, _ = AdditionalModel.objects.update_or_create(
                user=user,
                defaults=model_fields,
            )

            log.debug("configure_user: Updated model %s: %s", model_name, addl_model)
