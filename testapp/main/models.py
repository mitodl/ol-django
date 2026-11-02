"""Testapp models"""

from functools import cached_property

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property as django_cached_property
from mitol.common.models import (
    AuditableModel,
    AuditModel,
    CachedPropertiesMixin,
    PrefetchGenericQuerySet,
    TimestampedModel,
)
from mitol.common.utils.serializers import serialize_model_object


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
        return data  # noqa: RET504


class AuditableTestModelAudit(AuditModel):
    """Test-only model"""

    auditable_test_model = models.ForeignKey(
        AuditableTestModel, null=True, on_delete=models.SET_NULL
    )

    @classmethod
    def get_related_field_name(cls):
        return "auditable_test_model"


class CachedPropertyOwner(models.Model):
    """Test-only model: the forward relation a cached property derives from"""

    name = models.CharField(max_length=100)


class CachedPropertyParent:
    """Test-only plain parent class that contributes a cached property"""

    @cached_property
    def inherited_label(self):
        """A cached property reachable only through the MRO"""
        return f"<{self.title}>"


class CachedPropertyModel(CachedPropertiesMixin, CachedPropertyParent, models.Model):
    """Test-only model exercising CachedPropertiesMixin"""

    # `child_names` and `inherited_label` are deliberately left undeclared: a
    # narrowed refresh must not clear a property that has not opted in.
    cached_property_sources = {
        "owner_name": {"owner"},
        "child_count": {"children"},
    }

    title = models.CharField(max_length=100)
    note = models.TextField(default="")
    owner = models.ForeignKey(CachedPropertyOwner, on_delete=models.CASCADE)

    @cached_property
    def child_count(self):
        """Count the children - a functools-flavored cached property"""
        return self.children.count()

    @django_cached_property
    def child_names(self):
        """List the child names - a django.utils.functional-flavored one"""
        return sorted(self.children.values_list("name", flat=True))

    @cached_property
    def owner_name(self):
        """Read through the `owner` relation it declares as its source"""
        return self.owner.name


class CachedPropertyChild(models.Model):
    """Test-only model: the reverse relation a cached property derives from"""

    parent = models.ForeignKey(
        CachedPropertyModel, related_name="children", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)


class DemoCourseware(models.Model):
    """Testapp courseware"""

    title = models.CharField(max_length=100)
    description = models.TextField()

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
