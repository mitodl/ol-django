"""Testapp models"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from mitol.common.models import (
    ActiveUndeleteManager,
    AuditableModel,
    AuditModel,
    PrefetchGenericQuerySet,
    SoftDeleteModel,
    TimestampedModel,
)
from mitol.common.utils.serializers import serialize_model_object


class SecondLevel1(models.Model):
    """Test-only model"""


class SecondLevel2(models.Model):
    """Test-only model"""


class FirstLevel1(models.Model):
    """Test-only model"""

    second_level = models.ForeignKey(SecondLevel1, on_delete=models.CASCADE)


class FirstLevel2(models.Model):
    """Test-only model"""

    second_levels = models.ManyToManyField(SecondLevel2)


class TestModelQuerySet(PrefetchGenericQuerySet):
    """Test-only QuerySet"""


class Root(models.Model):
    """Test-only model"""

    objects = TestModelQuerySet.as_manager()

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")


class Updateable(TimestampedModel):
    """Test-only model"""


class AuditableTestModel(AuditableModel):
    """Test-only model"""

    @classmethod
    def get_audit_class(cls):
        return AuditableTestModelAudit

    def to_dict(self):
        """
        Get a serialized representation of the AuditableTestModel
        """
        data = serialize_model_object(self)
        return data


class AuditableTestModelAudit(AuditModel):
    """Test-only model"""

    auditable_test_model = models.ForeignKey(
        AuditableTestModel, null=True, on_delete=models.SET_NULL
    )

    @classmethod
    def get_related_field_name(cls):
        return "auditable_test_model"


class DemoCourseware(models.Model):
    """Testapp courseware"""

    title = models.CharField(max_length=100)
    description = models.TextField()

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class TestSoftDelete(SoftDeleteModel):
    """Test model for soft deletion"""

    test_data = models.CharField(max_length=100)

    all_objects = models.Manager()
    objects = ActiveUndeleteManager()


class TestSoftDeleteTimestamped(SoftDeleteModel, TimestampedModel):
    """Test model for soft deletions with timestamps"""

    test_data = models.CharField(max_length=100)

    all_objects = models.Manager()
    objects = ActiveUndeleteManager()
