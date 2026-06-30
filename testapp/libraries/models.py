from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

_ALLOWED_RECOMMENDATION_CONTENT_TYPES = {"book", "media", "periodical"}


class Author(models.Model):
    name = models.CharField(max_length=255)


class Topic(models.Model):
    name = models.CharField(max_length=255, unique=True)


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    topics = models.ManyToManyField(Topic, blank=True)


class Media(models.Model):
    title = models.CharField(max_length=255)
    authors = models.ManyToManyField(Author, blank=True)


class Periodical(models.Model):
    title = models.CharField(max_length=255)
    authors = models.ManyToManyField(Author, blank=True)


class Recommendation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    def clean(self):
        if (
            self.content_type_id
            and self.content_type.model not in _ALLOWED_RECOMMENDATION_CONTENT_TYPES
        ):
            allowed = ", ".join(sorted(_ALLOWED_RECOMMENDATION_CONTENT_TYPES))
            msg = f"Recommendation content type must be one of: {allowed}"
            raise ValidationError(msg)


class RecommendationList(models.Model):
    title = models.CharField(max_length=255)
    recommendations = models.ManyToManyField(Recommendation, blank=True)


class Library(models.Model):
    name = models.CharField(max_length=255)
    books = models.ManyToManyField(Book, blank=True)
    media = models.ManyToManyField(Media, blank=True)
    periodicals = models.ManyToManyField(Periodical, blank=True)
    recommendation_lists = models.ManyToManyField(RecommendationList, blank=True)
