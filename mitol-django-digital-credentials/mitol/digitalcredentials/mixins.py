"""View mixins"""
from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from mitol.digitalcredentials.serializers import DigitalCredentialRequestSerializer


class LearnerObjectModelViewSet(ModelViewSet):  # pragma: no cover
    # Note: this would ideally be typed with User as the return type, but mypy was uncooperative
    def get_learner_for_obj(self, obj: Any) -> Any:
        ...


if TYPE_CHECKING:  # pragma: no cover
    _Base = LearnerObjectModelViewSet
else:
    _Base = object


class DigitalCredentialsRequestViewSetMixin(_Base):
    """View mixin to create a digital credential request for a given resource object"""

    @action(
        detail=True,
        methods=["post"],
        url_path="request-digital-credential",
        url_name="request_digital_credentials",
    )
    def request_digital_credential(
        self, request: Request, pk=None
    ):  # pylint: disable=unused-argument
        """Action to create a digital credentials request"""
        credentialed_object = self.get_object()
        learner = self.get_learner_for_obj(credentialed_object)

        serializer = DigitalCredentialRequestSerializer(
            data={
                "credentialed_object_id": credentialed_object.id,
                "credentialed_content_type_id": ContentType.objects.get_for_model(
                    credentialed_object
                ).id,
                "learner_id": learner.id,
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
