"""Digital credentials factories"""
from django.contrib.contenttypes.models import ContentType
from factory import LazyAttribute, SelfAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory

from mitol.digitalcredentials.models import (
    DigitalCredential,
    DigitalCredentialRequest,
    LearnerDID,
)


class DigitalCredentialRequestFactory(DjangoModelFactory):
    """Factory for LearnerDID"""

    learner = SubFactory("mitol.common.factories.UserFactory")

    courseware_object_id = SelfAttribute("courseware_object.id")
    courseware_content_type = LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.courseware_object)
    )

    class Meta:
        model = DigitalCredentialRequest


class LearnerDIDFactory(DjangoModelFactory):
    """Factory for LearnerDID"""

    learner = SubFactory("mitol.common.factories.UserFactory")
    did = Sequence(lambda n: f"did:example:{n}")

    class Meta:
        model = LearnerDID


class DigitalCredentialFactory(DjangoModelFactory):
    """Factory for LearnerDID"""

    learner = SubFactory("mitol.common.factories.UserFactory")
    learner_did = SubFactory(LearnerDIDFactory, learner=SelfAttribute("..learner"))

    courseware_object_id = SelfAttribute("courseware_object.id")
    courseware_content_type = LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.courseware_object)
    )

    credential_json = "{}"

    class Meta:
        model = DigitalCredential
