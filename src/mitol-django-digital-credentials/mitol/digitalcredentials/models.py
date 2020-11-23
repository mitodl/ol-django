"""Digital credentials models"""
import uuid
from hashlib import sha256

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from mitol.common.models import TimestampedModel


class DigitalCredentialRequest(TimestampedModel):
    """Data model representing a request for digital credentials"""

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="digital_credential_requests",
    )

    courseware_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    courseware_object_id = models.PositiveIntegerField()
    courseware_object = GenericForeignKey(
        "courseware_content_type", "courseware_object_id"
    )

    consumed = models.BooleanField(default=False)

    def __str__(self):
        return f"Credential request uuid={self.uuid} learner={self.learner} courseware={self.courseware_object}"


class LearnerDID(TimestampedModel):
    """Association of a DID to a learner"""

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    did = models.TextField()
    # we include a hashed version of the DID for efficient lookups
    did_sha256 = models.CharField(max_length=64, unique=True)

    @staticmethod
    def sha256_hash_did(did: str) -> str:
        """Hashes a DID into sha256"""
        return sha256(did.encode("ascii")).hexdigest()

    def save(self, *args, **kwargs):  # pylint: disable=signature-differs
        """Override save() to hash the did"""
        self.did_sha256 = self.sha256_hash_did(self.did)
        return super().save(*args, **kwargs)


class DigitalCredential(TimestampedModel):
    """Data model representing a digital credential"""

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    learner_did = models.ForeignKey(LearnerDID, on_delete=models.CASCADE)

    courseware_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    courseware_object_id = models.PositiveIntegerField()
    courseware_object = GenericForeignKey(
        "courseware_content_type", "courseware_object_id"
    )

    credential_json = models.TextField()  # for now, just store the JSON as plaintext

    def __str__(self):
        return f"Digital credential learner={self.learner} did={self.learner_did.did} courseware={self.courseware_object}"
