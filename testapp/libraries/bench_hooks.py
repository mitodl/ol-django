"""
Seed hooks for the libraries benchmark — the escape hatch, demonstrated.

A declarative seed step covers counts, cycling and sampling. A hook covers
what it cannot: a distribution, a conditional attachment, a graph. It is
handed the knobs, every object built so far, the shared deterministic RNG,
and the same resolver the declarative steps use.
"""

from libraries.factories import BookFactory, TopicFactory


def skewed_books(context):
    """
    Attach books to authors on a long tail rather than evenly.

    ``$cycle`` spreads rows uniformly, which is exactly wrong for data where a
    few parents hold most of the children — and uniform fan-out hides the
    prefetch cost that a skewed one exposes.
    """
    authors = context.objects["authors"]
    total = context.knobs.get("books", 100)
    books = []
    for index in range(total):
        # The first author takes a quarter of the rows; the rest share what
        # is left, which is closer to how real catalogues look.
        position = 0 if index % 4 == 0 else 1 + (index % (len(authors) - 1))
        books.append(BookFactory.create(author=authors[position]))
    return books


def topics_for(context):
    """Create one topic per row the knobs ask for, named from the step."""
    return [
        TopicFactory.create(name=f"{context.step.name} {index}")
        for index in range(context.knobs.get("topics", 10))
    ]
