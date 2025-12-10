import factory
import factory.fuzzy
from factory.django import DjangoModelFactory


class AuthorFactory(DjangoModelFactory):
    name = factory.Faker("name")

    class Meta:
        model = "libraries.Author"


class BookFactory(DjangoModelFactory):
    title = factory.Faker("words")

    author = factory.SubFactory(AuthorFactory)

    class Meta:
        model = "libraries.Book"


class LibraryFactory(DjangoModelFactory):
    name = factory.fuzzy.FuzzyText(suffix=" Library")

    @factory.post_generation
    def books(self, create, extracted, **kwargs):
        extracted = extracted or BookFactory.create_batch(50, **kwargs)

        if not create:
            return

        self.books.add(*extracted)

    class Meta:
        model = "libraries.Library"
