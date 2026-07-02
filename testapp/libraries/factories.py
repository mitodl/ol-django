import factory
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory

from libraries.models import (
    Author,
    Book,
    Library,
    Media,
    Periodical,
    Recommendation,
    RecommendationList,
    Topic,
)


class AuthorFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Author {n}")

    class Meta:
        model = Author


class TopicFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Topic {n}")

    class Meta:
        model = Topic
        django_get_or_create = ("name",)


class BookFactory(DjangoModelFactory):
    title = factory.Sequence(lambda n: f"Book {n}")
    author = factory.SubFactory(AuthorFactory)

    class Meta:
        model = Book


class MediaFactory(DjangoModelFactory):
    title = factory.Sequence(lambda n: f"Media {n}")

    class Meta:
        model = Media


class PeriodicalFactory(DjangoModelFactory):
    title = factory.Sequence(lambda n: f"Periodical {n}")

    class Meta:
        model = Periodical


class RecommendationFactory(DjangoModelFactory):
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.content_object)
    )
    object_id = factory.SelfAttribute("content_object.pk")
    content_object = factory.SubFactory(BookFactory)

    class Meta:
        model = Recommendation
        exclude = ["content_object"]


class RecommendationListFactory(DjangoModelFactory):
    title = factory.Sequence(lambda n: f"RecommendationList {n}")

    class Meta:
        model = RecommendationList


class LibraryFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Library {n}")

    class Meta:
        model = Library
