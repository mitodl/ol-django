"""Views for transcoding app"""

import json

import requests
from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from mitol.transcoding.constants import BAD_REQUEST_MSG
from mitol.transcoding.exceptions import BadRequest
from mitol.transcoding.utils import get_subscribe_url


class TranscodeJobView(GenericAPIView):
    """Webhook endpoint for MediaConvert transcode job notifications from Cloudwatch"""

    permission_classes = (AllowAny,)

    def post(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):  # pylint: disable=unused-argument
        """Update Video and VideoFile objects based on request body"""
        message = json.loads(request.body)
        if message.get("SubscribeURL"):
            # Confirm the subscription
            if settings.AWS_ACCOUNT_ID not in message.get("TopicArn", ""):
                raise PermissionDenied

            token = message.get("Token", "")
            if not token:
                raise BadRequest(BAD_REQUEST_MSG)

            subscribe_url = get_subscribe_url(token)
            requests.get(subscribe_url, timeout=60)
        else:
            if message.get("account", "") != settings.AWS_ACCOUNT_ID:
                raise PermissionDenied
            detail = message.get("detail", {})

            for action in settings.POST_TRANSCODE_ACTIONS:
                import_string(action)(detail)

        return Response(status=200, data={})
