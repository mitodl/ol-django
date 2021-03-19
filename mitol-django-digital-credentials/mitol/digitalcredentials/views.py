"""Digital credential views"""
import json

from django.db import transaction
from oauth2_provider.contrib.rest_framework import OAuth2Authentication, TokenHasScope
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from mitol.digitalcredentials.serializers import DigitalCredentialIssueSerializer


class DigitalCredentialIssueView(GenericAPIView):
    """Digital credential API views"""

    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated, TokenHasScope]
    required_scopes = ["digitalcredentials"]
    serializer_class = DigitalCredentialIssueSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        """Get the set of credential requests for the current user"""
        learner = self.request.user

        return learner.digital_credential_requests.filter(consumed=False)

    def post(
        self, request: Request, *args, **kwargs
    ):  # pylint: disable=unused-argument
        """Consume the credential request for a verified credential"""
        # normally POST is only supported for DRF create operations
        # but we need to map the verb to an update, hence this custom view code

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)

        # wrap the serializer and the validation in a transaction
        # because of validate_learner_did
        with transaction.atomic():
            serializer.is_valid(raise_exception=True)
            credential = serializer.save()

        return Response(json.loads(credential.credential_json))
