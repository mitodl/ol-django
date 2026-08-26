mitol-django-common
---

This is the Open Learning Django Common app. It provides common functionality used across all our applications.

### Getting started

`pip install mitol-django-common`


### Configuration

- `MITOL_COMMON_USER_FACTORY` - (optional) set to the fully qualified path for a user model factory, otherwise a default based on `django.contrib.auth.models.User` is used

### `BaseSerializer` and `required_prefetches`

`mitol.common.serializers.BaseSerializer` is a `ModelSerializer` that makes the
queryset a view must build an explicit, checkable part of the serializer:

```python
from mitol.common.serializers import BaseSerializer


class BookSerializer(BaseSerializer):
    required_prefetches = ["author", "topics"]

    author = AuthorSerializer()

    class Meta:
        model = Book
        fields = ["id", "author", "topics"]
```

Every subclass must define `required_prefetches`; omitting it raises
`RequiredPrefetchesNotDefinedError` on instantiation. Before serializing,
`to_representation` checks each entry with
`mitol.common.utils.queryset.is_prefetched`, which recognises
`select_related()`, `prefetch_related()` and django-prefetch's `prefetch()`.
A missing prefetch raises `RequiredPrefetchMissingError` under `DEBUG` or
pytest, and logs a structured `RequiredPrefetchMissing` error in production
rather than turning a slow response into a 500.

Pass `context={"skip_prefetch_checks": THIS_IS_NOT_AN_API}` to opt a call site
out - intended for tests and non-API code only.

Entries must be plain field names. `is_prefetched` resolves them through
`Model._meta.get_field()` and the prefetch caches, neither of which understands
a traversal path, so `"author__books"` can never be satisfied.

[`mitol-drf-lint`](../drf_lint/README.md) checks all of this statically: it
reports a relation the serializer reads but never declares (`ORM007`), a
subclass with no declaration (`ORM008`), and an entry that can never be
satisfied (`ORM009`) - and it uses the declaration to stay quiet about
relation access that is provably already fetched.
