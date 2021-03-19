"""Testapp models"""
from django.conf import settings
from django.db import models


class DemoCourseware(models.Model):
    """Testapp courseware"""

    title = models.CharField(max_length=100)
    description = models.TextField()

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
