"""Authentication backends for the API Gateway."""

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend

from mitol.apigateway.api import decode_x_header

log = logging.getLogger(__name__)
User = get_user_model()


class ApisixRemoteUserBackend(RemoteUserBackend):
    """
    Custom RemoteUserBackend that updates users using the APISIX headers.

    RemoteUserBackend already has some support for creating an unknown user, but
    it won't fill out all the data we'll generally want to capture. Additionally,
    we'll want to toggle the user creation code with a setting.
    """

    create_unknown_user = settings.MITOL_APIGATEWAY_USERINFO_CREATE
    update_known_user = settings.MITOL_APIGATEWAY_USERINFO_UPDATE

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
            setattr(user, model_field, decoded_headers.get(header_field, None))

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
