"""Serializers for digital credentials"""
import json
import logging
from typing import Dict, cast

from rest_framework.serializers import CharField, Serializer, ValidationError

from mitol.digitalcredentials.backend import (
    build_credential,
    issue_credential,
    verify_presentations,
)
from mitol.digitalcredentials.models import DigitalCredential, LearnerDID


log = logging.getLogger(__name__)


class DigitalCredentialRequestSerializer(Serializer):
    """Serializer for digital credential requests"""

    id = CharField(write_only=True)

    def validate_id(self, value: str):
        """Validate the id (DID)"""
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
        did = cast(str, validated_data.get("id"))
        learner_did = LearnerDID.objects.get(did_sha256=LearnerDID.sha256_hash_did(did))

        credential = build_credential(instance.courseware_object, learner_did)
        credential_json = issue_credential(credential)

        # consume the request
        instance.consumed = True
        instance.save()

        return DigitalCredential.objects.create(
            learner=instance.learner,
            learner_did=learner_did,
            courseware_object=instance.courseware_object,
            credential_json=json.dumps(credential_json),
        )
