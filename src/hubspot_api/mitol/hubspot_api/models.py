""" Hubspot models """
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class HubspotObject(models.Model):
    """
    Stores the Hubspot ID for an object of a certain content type
    """

    hubspot_id = models.CharField(max_length=255, blank=False, null=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="hubspot_api_content_object_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["object_id", "content_type"],
                name="hubspot_api_unique_object_id_type",
            ),
            models.UniqueConstraint(
                fields=["hubspot_id", "content_type"],
                name="hubspot_api_unique_hubspot_id_type",
            ),
        ]
