"""Serializers for digital credentials"""
import json
import logging
from typing import Dict, cast

from rest_framework.serializers import (
    CharField,
    IntegerField,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
    UUIDField,
    ValidationError,
)

from mitol.digitalcredentials.backend import (
    build_credential,
    create_deep_link_url,
    issue_credential,
    verify_presentations,
)
from mitol.digitalcredentials.models import (
    DigitalCredential,
    DigitalCredentialRequest,
    LearnerDID,
)

log = logging.getLogger(__name__)


class DigitalCredentialIssueSerializer(Serializer):
    """Serializer for issuing digital credential"""

    holder = CharField(write_only=True)

    def validate_holder(self, value: str):
        """Validate the holder (DID)"""
        assert self.instance is not None
        learner = self.instance.learner
        learner_did, _ = LearnerDID.objects.get_or_create(
            did_sha256=LearnerDID.sha256_hash_did(value),
            defaults=dict(did=value, learner=learner),
        )

        if learner_did.learner_id != learner.id:
            raise ValidationError("DID is associated with someone else")

        return value

    def to_internal_value(self, data):
        """Override to_internal_value"""
        return {**data, **super().to_internal_value(data)}

    def validate(self, attrs):
        """Validate the data"""
        result = verify_presentations(self.instance, attrs)

        if not result.ok:
            log.debug("Failed to verify presentation: %s", result.json())
            raise ValidationError("Unable to verify digital credential presentation")

        return attrs

    def update(self, instance, validated_data: Dict):
        """Perform an update by consuming the credentials request"""

        # we associate the learner DID with the request's learner
        did = cast(str, validated_data.get("holder"))
        learner_did = LearnerDID.objects.get(did_sha256=LearnerDID.sha256_hash_did(did))

        credential = build_credential(instance.credentialed_object, learner_did)
        credential_json = issue_credential(credential)

        # consume the request
        instance.consumed = True
        instance.save()

        return DigitalCredential.objects.create(
            learner=instance.learner,
            learner_did=learner_did,
            credentialed_object=instance.credentialed_object,
            credential_json=json.dumps(credential_json),
        )


class DigitalCredentialRequestSerializer(ModelSerializer):
    """Serializer for DigitalCredentialRequest"""

    credentialed_object_id = IntegerField(write_only=True)
    credentialed_content_type_id = CharField(write_only=True)
    learner_id = IntegerField(write_only=True)
    deep_link_url = SerializerMethodField()
    uuid = UUIDField(read_only=True)

    def get_deep_link_url(self, instance: DigitalCredentialRequest) -> str:
        """Get the deep link url for the wallet app"""
        return create_deep_link_url(instance)

    class Meta:
        model = DigitalCredentialRequest
        fields = (
            "credentialed_object_id",
            "credentialed_content_type_id",
            "learner_id",
            "uuid",
            "deep_link_url",
        )
