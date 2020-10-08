"""Testapp models"""
from django.db import models


class DemoCourseware(models.Model):
    """Testapp courseware"""

    title = models.CharField(max_length=100)
    description = models.TextField()
