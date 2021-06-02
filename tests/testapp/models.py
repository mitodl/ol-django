"""Testapp models"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from mitol.common.models import PrefetchGenericQuerySet, TimestampedModel


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


class DemoCourseware(models.Model):
    """Testapp courseware"""

    title = models.CharField(max_length=100)
    description = models.TextField()

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
