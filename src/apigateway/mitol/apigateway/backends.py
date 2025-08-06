"""Authentication backends for the API Gateway."""

import contextlib
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend
from django.db import transaction

from mitol.apigateway.api import decode_x_header

log = logging.getLogger(__name__)
User = get_user_model()


class RemoteUserCustomFieldBackend(RemoteUserBackend):
    """
    RemoteUserBackend variant that allows the field for the lookup to be configured
    """

    lookup_field: str

    def authenticate(self, request, remote_user):
        """
        Authenticate the user
        """
        if not remote_user:
            return None
        created = False
        user = None
        username = self.clean_username(remote_user)

        if self.create_unknown_user:
            user, created = User.objects.get_or_create(**{self.lookup_field: username})
        else:
            with contextlib.suppress(User.DoesNotExist):
                user = User.objects.get_by_natural_key(username)
        user = self.configure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None

    async def aauthenticate(self, request, remote_user):
        """See authenticate()."""
        if not remote_user:
            return None
        created = False
        user = None
        username = self.clean_username(remote_user)

        if self.create_unknown_user:
            user, created = await User.objects.aget_or_create(
                **{self.lookup_field: username}
            )
        else:
            with contextlib.suppress(User.DoesNotExist):
                user = await User.objects.aget_by_natural_key(username)
        user = await self.aconfigure_user(request, user, created=created)
        return user if self.user_can_authenticate(user) else None


class ApisixRemoteUserBackend(RemoteUserCustomFieldBackend):
    """
    Custom RemoteUserBackend that updates users using the APISIX headers.

    RemoteUserBackend already has some support for creating an unknown user, but
    it won't fill out all the data we'll generally want to capture. Additionally,
    we'll want to toggle the user creation code with a setting.
    """

    lookup_field = "global_id"

    create_unknown_user = settings.MITOL_APIGATEWAY_USERINFO_CREATE
    update_known_user = settings.MITOL_APIGATEWAY_USERINFO_UPDATE

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
        """See authenticate()."""
        try:
            with transaction.atomic():
                return super().aauthenticate(request, remote_user)
        except Exception:
            log.exception("Unable to authenticate api gateway user")
            return None

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

        for header_field, model_field in infomap["user_fields"].items():
            value = decoded_headers.get(header_field, None)
            if isinstance(model_field, tuple):
                # If the model_field is a tuple, it means we have a flag for not
                # updating the value.
                model_field_name, override = model_field
                default_value = User._meta.get_field(model_field_name).get_default()  # noqa: SLF001
                field_not_set = getattr(user, model_field_name) == default_value
                if not override and not field_not_set:
                    continue
                setattr(user, model_field_name, value)
            else:
                setattr(user, model_field, value)

        user.save()

        log.debug("configure_user: Updated user %s", user)

        for model_name in infomap["additional_models"]:
            AdditionalModel = apps.get_model(model_name)
            model_fields = {
                "user": user,
            }

            for header_field, model_field, default_value in infomap[
                "additional_models"
            ][model_name]:
                model_fields[model_field] = decoded_headers.get(
                    header_field, default_value
                )

            addl_model, _ = AdditionalModel.objects.update_or_create(
                user=user,
                defaults=model_fields,
            )

            log.debug("configure_user: Updated model %s: %s", model_name, addl_model)

        return user
